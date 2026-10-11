"""The verifier has to fail on the things that actually go wrong."""

from __future__ import annotations

import dna_edit
import verify_product

START, END, NEW = 35, 50, "TTTTT"
DROP = ["middle"]


def _product(plasmid, tmp_path, **kw):
    path, seq = plasmid
    bb = dna_edit.Backbone(str(path))
    kw.setdefault("drop_features", DROP)
    out = tmp_path / "product.dna"
    out.write_bytes(dna_edit.build(bb, START, END, NEW, **kw))
    return str(path), str(out)


def test_a_correct_product_passes(plasmid, tmp_path):
    bbp, prp = _product(plasmid, tmp_path, add_feature=dict(name="insert"))
    assert verify_product.check(bbp, prp, START, END, NEW,
                                feature="insert", dropped=DROP) == []


def test_a_corrupted_base_is_caught(plasmid, tmp_path, dna_format):
    bbp, prp = _product(plasmid, tmp_path)
    blocks = dna_format.parse_blocks(open(prp, "rb").read())
    for i, b in enumerate(blocks):
        if b.type_id == 0:
            payload = bytearray(b.payload)
            payload[90] = ord("g") if payload[90] != ord("g") else ord("a")
            blocks[i] = dna_format.Block(0, bytes(payload))
    open(prp, "wb").write(dna_format.serialize_blocks(blocks))
    errs = verify_product.check(bbp, prp, START, END, NEW, dropped=DROP)
    assert any("flank" in e or "bases" in e for e in errs), errs


def test_the_wrong_insert_is_caught(plasmid, tmp_path):
    bbp, prp = _product(plasmid, tmp_path)
    errs = verify_product.check(bbp, prp, START, END, "TTTTA", dropped=DROP)
    assert any("inserted segment" in e for e in errs), errs


def test_an_oligo_that_does_not_occur_once_is_caught(plasmid, tmp_path):
    bbp, prp = _product(plasmid, tmp_path)
    errs = verify_product.check(bbp, prp, START, END, NEW, dropped=DROP,
                                oligos=["GGGGGGGGGGGGGGGGGGGG"])
    assert any("occurs" in e for e in errs), errs


def test_a_dropped_feature_is_not_demanded_back(plasmid, tmp_path):
    bbp, prp = _product(plasmid, tmp_path)
    assert verify_product.check(bbp, prp, START, END, NEW, dropped=DROP) == []
    errs = verify_product.check(bbp, prp, START, END, NEW, dropped=[])
    assert any("middle" in e for e in errs), errs


def test_feature_name_matching_ignores_non_ascii_decoding(plasmid, tmp_path):
    """"2xBbsI" arrives spelled differently depending on which reader supplied it."""
    assert verify_product._key("2×BbsI") == verify_product._key("2Ã—BbsI") == "2BbsI"
