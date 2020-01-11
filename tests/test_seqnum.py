from _pynetworktables._impl.storage import _Entry


def test_sequence_numbers():

    e = _Entry("name", 0, None)

    #
    # Test rollover
    #

    e.seq_num = 0xFFFE
    e.increment_seqnum()
    assert e.seq_num == 0xFFFF

    e.increment_seqnum()
    assert e.seq_num == 0

    #
    # test Entry.isSeqNewerThan
    # -> operator >
    #

    e.seq_num = 10
    assert e.isSeqNewerThan(20) == False

    e.seq_num = 20
    assert e.isSeqNewerThan(10) == True

    e.seq_num = 50000
    assert e.isSeqNewerThan(10) == False

    e.seq_num = 10
    assert e.isSeqNewerThan(50000) == True

    e.seq_num = 20
    assert e.isSeqNewerThan(20) == False

    e.seq_num = 50000
    assert e.isSeqNewerThan(50000) == False

    #
    # test Entry.isSeqNewerOrEqual
    # -> operator >=
    #

    e.seq_num = 10
    assert e.isSeqNewerOrEqual(20) == False

    e.seq_num = 20
    assert e.isSeqNewerOrEqual(10) == True

    e.seq_num = 50000
    assert e.isSeqNewerOrEqual(10) == False

    e.seq_num = 10
    assert e.isSeqNewerOrEqual(50000) == True

    e.seq_num = 20
    assert e.isSeqNewerOrEqual(20) == True

    e.seq_num = 50000
    assert e.isSeqNewerOrEqual(50000) == True
