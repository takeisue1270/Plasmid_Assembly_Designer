"""The splice itself: sequence arithmetic, feature shifting, primers, guards."""

from __future__ import annotations

import dna_edit
import pytest

# the edit window used throughout: 1-based 35..50 replaced by a 5 nt insert
START, END, NEW = 35, 50, "TTTTT"
DELTA = len(NEW) - (END - START + 1)          # 5 - 16 = -11
DROP = ["middle"]                             # the only feature overlapping 35..50


def _build(path, **kw):
    bb = dna_edit.Backbone(str(path))
    kw.setdefault("drop_features", DROP)
    return bb, dna_edit.build(bb, START, END, NEW, **kw)


def test_sequence_arithmetic(plasmid, tmp_path, dna_format):
    path, seq = plasmid
    bb, data = _build(path)
    out = dna_format.read_sequence_block(
        dna_format.find_block(dna_format.parse_blocks(data), 0))
    assert len(out.sequence) == len(seq) + DELTA
    assert out.sequence == seq[:START - 1] + NEW + seq[END:]
    assert out.sequence[:START - 1] == seq[:START - 1]       # upstream flank intact
    assert out.sequence[START - 1 + len(NEW):] == seq[END:]  # downstream flank intact
    assert out.circular


def test_features_before_the_window_do_not_move(plasmid, dna_format):
    path, _ = plasmid
    _, data = _build(path)
    xml = dna_format.find_block(dna_format.parse_blocks(data), 10).payload.decode("latin1")
    assert 'range="1-20"' in xml


def test_features_after_the_window_shift_by_delta(plasmid, dna_format):
    path, _ = plasmid
    _, data = _build(path)
    xml = dna_format.find_block(dna_format.parse_blocks(data), 10).payload.decode("latin1")
    assert f'range="{60 + DELTA}-{80 + DELTA}"' in xml
    assert 'range="60-80"' not in xml


def test_overlapping_feature_must_be_dropped(plasmid):
    """Silently shifting a feature that straddles the edit is the dangerous case."""
    path, _ = plasmid
    bb = dna_edit.Backbone(str(path))
    with pytest.raises(SystemExit, match="inside the replaced region"):
        dna_edit.build(bb, START, END, NEW, drop_features=[])


def test_dropping_an_absent_feature_is_an_error(plasmid):
    path, _ = plasmid
    bb = dna_edit.Backbone(str(path))
    with pytest.raises(SystemExit, match="not found"):
        dna_edit.build(bb, START, END, NEW, drop_features=["nope"])


def test_added_feature_covers_exactly_the_insert(plasmid, dna_format):
    path, _ = plasmid
    _, data = _build(path, add_feature=dict(name="insert"))
    xml = dna_format.find_block(dna_format.parse_blocks(data), 10).payload.decode("latin1")
    assert 'name="insert"' in xml
    assert f'range="{START}-{START - 1 + len(NEW)}"' in xml


def test_added_cds_feature_is_translated(plasmid, dna_format):
    path, _ = plasmid
    _, data = _build(path, add_feature=dict(name="orf", type="CDS"))
    xml = dna_format.find_block(dna_format.parse_blocks(data), 10).payload.decode("latin1")
    assert 'name="orf"' in xml and 'type="CDS"' in xml
    assert 'translated="1"' in xml and "codon_start" in xml


def test_primers_shift_with_the_sequence(plasmid, dna_format):
    path, _ = plasmid
    _, data = _build(path)
    xml = dna_format.find_block(dna_format.parse_blocks(data), 5).payload.decode("latin1")
    assert f'location="{60 + DELTA}-{79 + DELTA}"' in xml


def test_strip_primers_empties_the_block(plasmid, dna_format):
    path, _ = plasmid
    _, data = _build(path, strip_primers=True)
    xml = dna_format.find_block(dna_format.parse_blocks(data), 5).payload.decode("latin1")
    assert "<Primer " not in xml
    assert "</Primers>" in xml      # the container survives for the registrar to refill


def test_dropped_blocks_are_removed_and_kept_blocks_survive(plasmid, dna_format):
    path, _ = plasmid
    bb = dna_edit.Backbone(str(path))
    keep, drop = dna_edit.block_sets(bb.cfg)
    _, data = _build(path)
    present = {b.type_id for b in dna_format.parse_blocks(data)}
    assert not (present & drop)
    assert {9, 0, 10, 5, 6} <= present


def test_notes_get_a_fresh_uuid_and_description(plasmid, dna_format):
    path, _ = plasmid
    _, data = _build(path, description="product")
    notes = dna_format.find_block(dna_format.parse_blocks(data), 6).payload.decode("utf8")
    assert "<Description>product</Description>" in notes
    assert "00000000-0000-0000-0000-000000000000" not in notes


def test_region_outside_the_sequence_is_rejected(plasmid):
    path, seq = plasmid
    bb = dna_edit.Backbone(str(path))
    with pytest.raises(SystemExit, match="outside"):
        dna_edit.build(bb, 1, len(seq) + 1, NEW)


def test_insert_longer_than_the_region_shifts_the_other_way(plasmid, dna_format):
    path, seq = plasmid
    bb = dna_edit.Backbone(str(path))
    long_insert = "A" * 40
    data = dna_edit.build(bb, START, END, long_insert, drop_features=DROP)
    out = dna_format.read_sequence_block(
        dna_format.find_block(dna_format.parse_blocks(data), 0))
    assert len(out.sequence) == len(seq) + 40 - (END - START + 1)
    xml = dna_format.find_block(dna_format.parse_blocks(data), 10).payload.decode("latin1")
    assert f'range="{60 + 24}-{80 + 24}"' in xml
