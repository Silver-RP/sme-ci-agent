import socket

import pytest
import yaml

from backend.agent.llm import (
    AnthropicLLM,
    LLMConfigError,
    LLMResponse,
    ScriptedLLM,
    ScriptExhaustedError,
    ToolCall,
    ToolSpec,
)
from backend.agent.prompts import build_system_prompt
from backend.domain_config import DEFAULT_PROFILE_PATH, load_domain_config


def _cfg_file(tmp_path, mutate):
    data = yaml.safe_load(DEFAULT_PROFILE_PATH.read_text(encoding="utf-8"))
    mutate(data)
    p = tmp_path / "p.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return load_domain_config(p)


def test_prompt_contains_yaml_kpis_and_groups():
    cfg = load_domain_config()
    prompt = build_system_prompt(cfg)
    for k in cfg.kpis:
        assert k.name in prompt
    for g, causes in cfg.hypothesis_groups.items():
        assert g in prompt
        for c in causes:
            assert c in prompt
    assert cfg.domain in prompt
    assert "5 Whys" in prompt
    assert "ask" in prompt.lower()


def test_prompt_changes_with_yaml(tmp_path):
    def mutate(d):
        d["kpis"] = [{"name": "zz_kpi_x", "unit": "ratio", "target": 0.1, "alert_threshold_sd": 2}]
        d["hypothesis_groups"] = {"qq_group": ["qq_cause"]}
        d["domain"] = "logistics"

    prompt = build_system_prompt(_cfg_file(tmp_path, mutate))
    assert "zz_kpi_x" in prompt and "qq_group" in prompt and "qq_cause" in prompt
    assert "logistics" in prompt
    assert "defect_rate" not in prompt and "machine" not in prompt


def test_prompt_default_config_loads():
    assert "defect_rate" in build_system_prompt()


def test_prompt_module_has_no_hardcoded_names():
    from pathlib import Path

    import backend.agent.prompts as pkg

    src = "".join(p.read_text(encoding="utf-8") for p in Path(pkg.__file__).parent.glob("*.py"))
    for word in ["defect_rate", "rework_rate", "wrong_setpoint", "ishikawa_machine"]:
        assert word not in src


def test_real_llm_requires_model_env(monkeypatch):
    monkeypatch.delenv("MODEL_REASONING", raising=False)
    with pytest.raises(LLMConfigError, match="MODEL_REASONING"):
        AnthropicLLM()
    monkeypatch.setenv("MODEL_REASONING", "   ")
    with pytest.raises(LLMConfigError, match="MODEL_REASONING"):
        AnthropicLLM()


def test_real_llm_uses_env_model_without_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network used")

    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setenv("MODEL_REASONING", "model-from-env")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    llm = AnthropicLLM()
    assert llm.model == "model-from-env"
    monkeypatch.setenv("MODEL_CHEAP", "cheap-env")
    assert AnthropicLLM(model_env="MODEL_CHEAP").model == "cheap-env"


def test_real_llm_builds_request_and_parses_response():
    class Block:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class Resp:
        content = (Block(type="text", text="hi"), Block(type="tool_use", id="t1", name="correlate", input={"a": 1}))

    seen = {}

    class Msgs:
        def create(self, **kw):
            seen.update(kw)
            return Resp()

    class Client:
        messages = Msgs()

    llm = AnthropicLLM(model="m", client=Client())
    tools = [ToolSpec(name="correlate", description="d", input_schema={"type": "object"})]
    out = llm.complete("sys", [{"role": "user", "content": "go"}], tools)
    assert seen["model"] == "m" and seen["system"] == "sys"
    assert seen["tools"][0]["name"] == "correlate"
    assert out.text == "hi"
    assert out.tool_calls == [ToolCall(id="t1", name="correlate", arguments={"a": 1})]


def test_scripted_order_and_exhaustion():
    llm = ScriptedLLM(
        [
            LLMResponse(tool_calls=[ToolCall(id="1", name="correlate", arguments={})]),
            "final text",
        ]
    )
    r1 = llm.complete("s", [{"role": "user", "content": "x"}], [])
    assert r1.tool_calls[0].name == "correlate"
    r2 = llm.complete("s", [], [])
    assert r2.text == "final text" and r2.tool_calls == []
    with pytest.raises(ScriptExhaustedError):
        llm.complete("s", [], [])
    assert len(llm.calls) == 3  # the failing call is recorded too


def test_scripted_instances_do_not_share_state():
    script = ["a", "b"]
    l1, l2 = ScriptedLLM(script), ScriptedLLM(script)
    assert l1.complete("s", [], []).text == "a"
    assert l2.complete("s", [], []).text == "a"
    assert script == ["a", "b"]


def test_scripted_empty_script_errors():
    with pytest.raises(ScriptExhaustedError):
        ScriptedLLM([]).complete("s", [], [])
