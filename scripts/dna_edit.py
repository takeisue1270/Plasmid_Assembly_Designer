"""Splice a SnapGene .dna file: replace a region of the backbone and fix up the map.

Library + thin CLI. The coordinate contract everywhere in this module:

    replace the 1-based inclusive region [start, end] of the backbone with `new`

    product = seq[:start-1] + new + seq[end:]          # 0-based slices
    delta   = len(new) - (end - start + 1)

Features (1-based, `range="A-B"`): coordinates <= start-1 keep their value,
coordinates >  end   gain `delta`, and anything in between belongs to a feature
that overlaps the replaced region and must be named in `drop_features`.

Primers (0-based, `location=` / `hybridizedRange=`): <= start-2 unchanged,
>= end shifted. For a large replacement pass strip_primers=True instead and let
register_primers.py rebuild the block from the spreadsheet.

The features block is NOT valid UTF-8 (Japanese notes are Shift-JIS bytes), so
it is decoded and re-encoded as latin1 to keep the round trip byte-exact.
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as _config  # noqa: E402

SEQUENCE, PRIMERS, NOTES, FEATURES = 0, 5, 6, 10

_df = None


def df(cfg=None):
    """The snapgene-primer-registrar dna_format module.

    Imported lazily and from a configured location, so neither the checkout
    path nor the fact that it exists is baked into this file.
    """
    global _df
    if _df is None:
        sys.path.insert(0, str((cfg or _config.load()).registrar))
        from snapgene_primers import dna_format
        _df = dna_format
    return _df


def block_sets(cfg=None):
    """(keep, drop) block type ids. The map itself is kept; the parent's cache,
    history and sequencing alignments are dropped."""
    b = (cfg or _config.load())["dna_blocks"]
    return set(b["keep"]), set(b["drop"])


class Backbone:
    def __init__(self, path, cfg=None):
        self.cfg = cfg or _config.load()
        self.path = path
        df_ = df(self.cfg)
        KEEP_BLOCKS, DROP_BLOCKS = block_sets(self.cfg)
        self.blocks = df_.parse_blocks(open(path, "rb").read())
        unknown = {b.type_id for b in self.blocks} - KEEP_BLOCKS - DROP_BLOCKS
        if unknown:
            raise SystemExit(f"unhandled block types {sorted(unknown)} in {path}")
        self._seqblk = df_.find_block(self.blocks, SEQUENCE)
        info = df_.read_sequence_block(self._seqblk)
        self.seq = info.sequence
        self.circular = info.circular
        self.features = df_.find_block(self.blocks, FEATURES).payload.decode("latin1")
        self.primers = df_.find_block(self.blocks, PRIMERS).payload.decode("latin1")
        self.notes = df_.find_block(self.blocks, NOTES).payload.decode("utf8")

    def feature_names(self):
        return re.findall(r'<Feature [^>]*name="([^"]*)"', self.features)


def _shift_features(xml, start, end, delta):
    def rep(m):
        out = []
        for v in (int(m.group(1)), int(m.group(2))):
            if v <= start - 1:
                out.append(v)
            elif v > end:
                out.append(v + delta)
            else:
                raise SystemExit(
                    f"feature coordinate {v} lies inside the replaced region "
                    f"{start}..{end}; name that feature in drop_features")
        return f'range="{out[0]}-{out[1]}"'
    return re.sub(r'range="(\d+)-(\d+)"', rep, xml)


def _shift_primers(xml, start, end, delta):
    def rep(m):
        key = m.group(1)
        out = []
        for v in (int(m.group(2)), int(m.group(3))):
            if v <= start - 2:
                out.append(v)
            elif v >= end:
                out.append(v + delta)
            else:
                raise SystemExit(f"primer coordinate {v} lies inside the replaced region")
        return f'{key}="{out[0]}-{out[1]}"'
    return re.sub(r'(location|hybridizedRange)="(\d+)-(\d+)"', rep, xml)


def _drop_feature(xml, name):
    pat = re.compile(
        rf'<Feature recentID="(\d+)" name="{re.escape(name)}"[^>]*>.*?</Feature>', re.S)
    m = pat.search(xml)
    if not m:
        raise SystemExit(f"feature {name!r} not found")
    if len(pat.findall(xml)) != 1:
        raise SystemExit(f"feature {name!r} is not unique")
    return xml[:m.start()] + xml[m.end():], m.group(1)


def build(backbone, start, end, new, *, drop_features=(), add_feature=None,
          strip_primers=False, description=None, recent_id="900"):
    """Return the bytes of the spliced .dna.

    add_feature: dict(name=, type='misc_feature', color='#ffff99',
                      directionality='1', start=, end=)  -- 1-based, product
                 coordinates. Defaults to covering exactly the inserted segment.
    """
    seq = backbone.seq
    if not (1 <= start <= end <= len(seq)):
        raise SystemExit(f"region {start}..{end} outside 1..{len(seq)}")
    delta = len(new) - (end - start + 1)
    product = seq[:start - 1] + new + seq[end:]
    assert len(product) == len(seq) + delta
    assert product[:start - 1] == seq[:start - 1]
    assert product[start - 1 + len(new):] == seq[end:]

    xml = backbone.features
    freed = None
    for name in drop_features:
        xml, freed = _drop_feature(xml, name)
    xml = _shift_features(xml, start, end, delta)

    if add_feature:
        f = dict(type="misc_feature", color=backbone.cfg["gga"]["insert_feature_color"],
                 directionality="1", start=start, end=start - 1 + len(new))
        f.update(add_feature)
        rid = f.get("recentID", freed or recent_id)
        translated = ' translated="1"' if f["type"] == "CDS" else ""
        extra = '<Q name="codon_start"><V int="1"/></Q>' if f["type"] == "CDS" else ""
        el = (f'<Feature recentID="{rid}" name="{f["name"]}"'
              f' directionality="{f["directionality"]}" type="{f["type"]}"'
              f' allowSegmentOverlaps="0" consecutiveTranslationNumbering="1">'
              f'<Segment range="{f["start"]}-{f["end"]}" color="{f["color"]}"'
              f' type="standard"{translated}/>{extra}</Feature>')
        if "</Features>" not in xml:
            raise SystemExit("features block has no </Features>")
        xml = xml.replace("</Features>", el + "</Features>")

    if strip_primers:
        prim = re.sub(r"<Primer\b.*</Primer>", "", backbone.primers, flags=re.S)
        if "<Primer " in prim:
            raise SystemExit("failed to strip the primers block")
    else:
        prim = _shift_primers(backbone.primers, start, end, delta)

    notes = re.sub(r"<UUID>[^<]*</UUID>", f"<UUID>{uuid.uuid4()}</UUID>", backbone.notes)
    if description is not None:
        notes = re.sub(r"<Description>[^<]*</Description>",
                       f"<Description>{description}</Description>", notes)
    stamp = datetime.date.today().strftime("%Y.%#m.%#d" if os.name == "nt" else "%Y.%-m.%-d")
    notes = re.sub(r'<LastModified UTC="[^"]*">[^<]*</LastModified>',
                   f'<LastModified UTC="0:0:0">{stamp}</LastModified>', notes)

    df_ = df(backbone.cfg)
    _, DROP_BLOCKS = block_sets(backbone.cfg)
    out = []
    for b in backbone.blocks:
        if b.type_id in DROP_BLOCKS:
            continue
        if b.type_id == SEQUENCE:
            out.append(df_.Block(SEQUENCE, bytes([b.payload[0]]) + product.encode("ascii")))
        elif b.type_id == FEATURES:
            out.append(df_.Block(FEATURES, xml.encode("latin1")))
        elif b.type_id == PRIMERS:
            out.append(df_.Block(PRIMERS, prim.encode("latin1")))
        elif b.type_id == NOTES:
            out.append(df_.Block(NOTES, notes.encode("utf8")))
        else:
            out.append(b)
    return df_.serialize_blocks(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    _config.add_arguments(ap)
    ap.add_argument("--backbone", required=True,
                    help="source .dna; a bare name is looked up in the configured plasmid dir")
    ap.add_argument("--out", required=True, help="output .dna")
    ap.add_argument("--start", type=int, required=True, help="1-based first base replaced")
    ap.add_argument("--end", type=int, required=True, help="1-based last base replaced")
    ap.add_argument("--new", required=True, help="replacement sequence, or @file")
    ap.add_argument("--drop-feature", action="append", default=[],
                    help="feature name that overlaps the replaced region; repeatable")
    ap.add_argument("--feature-name", help="name of the feature to annotate on the insert")
    ap.add_argument("--feature-type", default="misc_feature")
    ap.add_argument("--feature-color", help="default: gga.insert_feature_color from config")
    ap.add_argument("--strip-primers", action="store_true",
                    help="empty the primers block; rebuild it with register_primers.py")
    ap.add_argument("--description", help="Notes <Description> for the product")
    ap.add_argument("--list-features", action="store_true", help="print feature names and exit")
    a = ap.parse_args()

    cfg = _config.from_arguments(a)
    src = a.backbone
    if not os.path.isfile(src):
        src = str(cfg.path("plasmid_dir") / a.backbone)
    bb = Backbone(src, cfg)
    if a.list_features:
        for n in bb.feature_names():
            print(n)
        return
    new = open(a.new[1:]).read().split() if a.new.startswith("@") else [a.new]
    new = "".join(new)
    color = a.feature_color or cfg["gga"]["insert_feature_color"]
    add = dict(name=a.feature_name, type=a.feature_type,
               color=color) if a.feature_name else None
    data = build(bb, a.start, a.end, new, drop_features=a.drop_feature,
                 add_feature=add, strip_primers=a.strip_primers,
                 description=a.description)
    open(a.out, "wb").write(data)
    delta = len(new) - (a.end - a.start + 1)
    print(f"wrote {a.out}  {len(bb.seq) + delta} bp "
          f"(backbone {len(bb.seq)} bp, delta {delta:+d})")


if __name__ == "__main__":
    main()
