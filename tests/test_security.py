from utils.security import hash_password, verify_password


def test_hash_roundtrip():
    stored = hash_password("Correct-Horse-1")
    assert verify_password("Correct-Horse-1", stored)


def test_wrong_password_rejected():
    stored = hash_password("Correct-Horse-1")
    assert not verify_password("wrong-password", stored)


def test_two_hashes_of_same_password_differ():
    # Random salt per call -> stored hashes must not be identical, but both
    # must still verify.
    a, b = hash_password("same-password"), hash_password("same-password")
    assert a != b
    assert verify_password("same-password", a)
    assert verify_password("same-password", b)


def test_malformed_stored_hash_is_rejected_not_crashed():
    assert not verify_password("anything", "not-a-valid-stored-hash")
