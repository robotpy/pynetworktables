
from ntcore.storage import _Entry

def test_sequence_numbers():
    
    e = _Entry('name')
    
    #
    # Test rollover
    #
    
    e.seq_num = 0xfffe
    e.increment_seqnum()
    assert e.seq_num == 0xffff
    
    e.increment_seqnum()
    assert e.seq_num == 0
    
    #
    # test Entry.isSeqNewerThan
    #
    
    e.seq_num = 10
    assert e.isSeqNewerThan(20) == False
    
    e.seq_num = 20
    assert e.isSeqNewerThan(10) == True
    
    e.seq_num = 50000
    assert e.isSeqNewerThan(10) == False
    
    e.seq_num = 10
    assert e.isSeqNewerThan(50000) == True
    