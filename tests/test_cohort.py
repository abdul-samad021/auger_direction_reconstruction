from auger_reco.data.cohort import _hash_rank, _split_for_event


def test_hash_rank_is_deterministic():
    assert _hash_rank(81847956000, 20260826, "pilot") == _hash_rank(81847956000, 20260826, "pilot")


def test_split_is_stable_and_valid():
    split = _split_for_event(81847956000, 20260826, 0.70, 0.15)
    assert split in {"train", "validation", "test"}
    assert split == _split_for_event(81847956000, 20260826, 0.70, 0.15)
