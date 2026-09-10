import pytest
import datetime
from processing.deadlines import extract_deadlines_heuristic

def test_extract_deadlines_due_tomorrow():
    ref_date = datetime.datetime(2026, 9, 10, 10, 0, 0)
    text = "Please note your assignment is due tomorrow."
    
    deadlines = extract_deadlines_heuristic(text, ref_date)
    assert len(deadlines) > 0
    assert deadlines[0]["deadline_date"].day == 11
    assert deadlines[0]["deadline_date"].month == 9

def test_extract_deadlines_explicit_date():
    ref_date = datetime.datetime(2026, 9, 10, 10, 0, 0)
    text = "Application deadline: September 15."
    
    deadlines = extract_deadlines_heuristic(text, ref_date)
    assert len(deadlines) > 0
    assert deadlines[0]["deadline_date"].day == 15
    assert deadlines[0]["deadline_date"].month == 9
