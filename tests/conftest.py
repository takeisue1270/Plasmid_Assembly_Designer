"""Offline fixtures: a synthetic SnapGene .dna built in-process.

No workbook, no Excel, no network. The only external piece is
snapgene-primer-registrar's dna_format, which is resolved the same way the
scripts resolve it (config.registrar, so a checkout beside this repository is
found automatically).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

COOKIE = b"SnapGene\x00\x01\x00\x0f\x00\x10"

NOTES = (
    "<Notes>\n<UUID>00000000-0000-0000-0000-000000000000</UUID>\n"
    "<Type>Synthetic</Type>\n<Description>backbone</Description>\n"
    '<LastModified UTC="0:0:0">2026.1.1</LastModified>\n</Notes>\n'
)

PRIMERS_EMPTY = (
    '<?xml version="1.0"?><Primers nextValidID="1">'
    '<HybridizationParams minContinuousMatchLen="10" allowMismatch="1"'
    ' minMeltingTemperature="40"/></Primers>\n'
)


def _primer(name, seq, a, b):
    """One <Primer> with a binding site at 0-based inclusive a..b."""
    return (
        f'<Primer recentID="0" name="{name}" sequence="{seq}">'
        f'<BindingSite location="{a}-{b}" boundStrand="0" annealedBases="{seq}"'
        f' meltingTemperature="50">'
        f'<Component hybridizedRange="{a}-{b}" bases="{seq}"/></BindingSite></Primer>'
    )


def _feature(rid, name, start, end, ftype="misc_feature", color="#ff0000"):
    """One <Feature> covering 1-based inclusive start..end."""
    return (
        f'<Feature recentID="{rid}" name="{name}" directionality="1" type="{ftype}"'
        f' allowSegmentOverlaps="0" consecutiveTranslationNumbering="1">'
        f'<Segment range="{start}-{end}" color="{color}" type="standard"/></Feature>'
    )


@pytest.fixture(scope="session")
def dna_format():
    import config
    sys.path.insert(0, str(config.load().registrar))
    try:
        from snapgene_primers import dna_format as df
    except ImportError:  # pragma: no cover
        pytest.skip("snapgene-primer-registrar not available")
    return df


@pytest.fixture
def make_dna(dna_format, tmp_path):
    """make_dna(sequence, features=[(name, start, end), ...], primers=[...]) -> path."""
    def _make(sequence, features=(), primers=(), name="backbone.dna"):
        feats = "".join(_feature(i, n, s, e) for i, (n, s, e) in enumerate(features))
        fxml = (f'<?xml version="1.0"?><Features nextValidID="{len(features) + 1}">'
                f"{feats}</Features>\n")
        if primers:
            pxml = PRIMERS_EMPTY.replace(
                "</Primers>", "".join(_primer(*p) for p in primers) + "</Primers>")
        else:
            pxml = PRIMERS_EMPTY
        blocks = [
            dna_format.Block(9, COOKIE),
            dna_format.Block(0, b"\x01" + sequence.encode("ascii")),
            dna_format.Block(10, fxml.encode("latin1")),
            dna_format.Block(5, pxml.encode("latin1")),
            dna_format.Block(6, NOTES.encode("utf8")),
        ]
        path = tmp_path / name
        path.write_bytes(dna_format.serialize_blocks(blocks))
        return path
    return _make


@pytest.fixture
def plasmid(make_dna):
    """A 120 bp circular plasmid.

    1..20   feature "left"      (before the edit window)
    30..45  feature "middle"    (overlaps the edit window 35..50)
    60..80  feature "right"     (after the edit window)
    """
    seq = ("aaaaaaaaaaaaaaaaaaaa"   # 1-20
           "cccccccccc"             # 21-30
           "gggggggggggggggggggg"   # 31-50
           "tttttttttt"             # 51-60
           "acgtacgtacgtacgtacgt"   # 61-80
           "cagtcagtcagtcagtcagtcagtcagtcagtcagtcagt")  # 81-120
    assert len(seq) == 120
    return make_dna(seq, features=[("left", 1, 20), ("middle", 30, 45), ("right", 60, 80)],
                    primers=[("p_far", "acgtacgtacgtacgtacgt", 60, 79)]), seq
