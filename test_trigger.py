from trigger import find_trigger

# Real results from a run on a test dump
HIT = {'result': [{'conf': 1.0, 'end': 22.53, 'start': 20.16, 'word': '[unk]'}, {'conf': 1.0, 'end': 23.34, 'start': 22.95, 'word': 'clip'}, {'conf': 1.0, 'end': 23.64, 'start': 23.34, 'word': 'that'}], 'text': '[unk] clip that'}
STRAY_THAT = {'result': [{'conf': 0.641917, 'end': 11.134786, 'start': 10.08, 'word': '[unk]'}, {'conf': 1.0, 'end': 12.579714, 'start': 11.134786, 'word': '[unk]'}, {'conf': 0.534022, 'end': 13.01423, 'start': 12.828576, 'word': 'that'}, {'conf': 0.846618, 'end': 14.43, 'start': 13.01423, 'word': '[unk]'}], 'text': '[unk] [unk] that [unk]'}
ALL_UNK = {'result': [{'conf': 1.0, 'end': 16.05, 'start': 15.42, 'word': '[unk]'}, {'conf': 1.0, 'end': 18.06, 'start': 16.68, 'word': '[unk]'}, {'conf': 1.0, 'end': 20.16, 'start': 18.81, 'word': '[unk]'}], 'text': '[unk] [unk] [unk]'}
FINAL_EMPTY = {'text': ''}


def w(word, start, end, conf=1.0):
    return {'word': word, 'start': start, 'end': end, 'conf': conf}


def test_real_hit_returns_when_the_phrase_ended():
    assert find_trigger(HIT) == 23.64

def test_lone_that_does_not_trigger():
    assert find_trigger(STRAY_THAT) is None

def test_all_unknown_does_not_trigger():
    assert find_trigger(ALL_UNK) is None

def test_result_with_no_words_does_not_crash():
    assert find_trigger(FINAL_EMPTY) is None

def test_unknown_word_between_clip_and_that_does_not_trigger():
    result = {'result': [w('clip', 1.0, 1.3), w('[unk]', 1.3, 1.6), w('that', 1.6, 1.9)]}
    assert find_trigger(result) is None

def test_low_confidence_does_not_trigger():
    result = {'result': [w('clip', 1.0, 1.3, 0.5), w('that', 1.3, 1.6, 0.5)]}
    assert find_trigger(result) is None

def test_one_low_confidence_word_is_enough_to_reject():
    result = {'result': [w('clip', 1.0, 1.3, 1.0), w('that', 1.3, 1.6, 0.5)]}
    assert find_trigger(result) is None

def test_wrong_order_does_not_trigger():
    result = {'result': [w('that', 1.0, 1.3), w('clip', 1.3, 1.6)]}
    assert find_trigger(result) is None

def test_custom_threshold_is_respected():
    result = {'result': [w('clip', 1.0, 1.3, 0.6), w('that', 1.3, 1.6, 0.6)]}
    assert find_trigger(result, min_conf=0.5) == 1.6
    assert find_trigger(result, min_conf=0.9) is None