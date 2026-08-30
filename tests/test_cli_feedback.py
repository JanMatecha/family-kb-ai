import builtins

from family_kb_ai import cli


def test_useful_results_prompt_accepts_multiple_ranks(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda _: "1,3,4")

    assert cli._prompt_useful_ranks(5) == (1, 3, 4)


def test_useful_results_prompt_can_go_back(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda _: "b")

    assert cli._prompt_useful_ranks(5) is cli._BACK


def test_useful_results_prompt_accepts_czech_back_word(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda _: "zpět")

    assert cli._prompt_useful_ranks(5) is cli._BACK
