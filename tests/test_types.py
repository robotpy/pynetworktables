import pytest
from _pynetworktables.entry import NetworkTableEntry


@pytest.mark.parametrize(
    "data, expected_result",
    [
        ("a", True),
        (1, True),
        (1.0, True),
        (1.0j, False),
        (False, True),
        (b"1", True),
        (bytearray(), True),
        ((), ValueError),
        ([], ValueError),
    ],
)
def test_isValidType(data, expected_result):
    if isinstance(expected_result, bool):
        assert NetworkTableEntry.isValidDataType(data) == expected_result
    else:
        with pytest.raises(expected_result):
            NetworkTableEntry.isValidDataType(data)
