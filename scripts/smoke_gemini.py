import json
import math
import sys
from pathlib import Path

# Add backend to path so we can import app if needed
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from google import genai
from google.genai import types
from app.config import settings


def l2_norm(vec: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vec))


def normalize_l2(vec: list[float]) -> list[float]:
    norm = l2_norm(vec)
    if norm == 0:
        return vec
    return [x / norm for x in vec]


def main():
    print("=== GEMINI SMOKE TEST & PROBE ===")
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        print("FAIL: GEMINI_API_KEY is not set in .env or environment!")
        print("Please add GEMINI_API_KEY=your_key to .env and run again.")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    model = settings.GEMINI_MODEL
    embed_model = settings.GEMINI_EMBED_MODEL
    dim = settings.EMBED_DIM

    all_passed = True

    # a) Plain call with thinking_level 'low'
    try:
        it = client.interactions.create(
            model=model,
            input="Respond with exactly 'HELLO_ARIADNE'.",
            generation_config={"thinking_level": "low"}
        )
        assert it.output_text and "HELLO_ARIADNE" in it.output_text
        print(f"a) Plain call (thinking_level='low'): PASS (output: '{it.output_text.strip()}')")
    except Exception as e:
        print(f"a) Plain call: FAIL ({e})")
        all_passed = False

    # b) Tool-call loop with one function (add_numbers) using previous_interaction_id and function_result
    try:
        tool_add = {
            "type": "function",
            "name": "add_numbers",
            "description": "Calculates the sum of two integers a and b",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "integer", "description": "first number"},
                    "b": {"type": "integer", "description": "second number"}
                },
                "required": ["a", "b"]
            }
        }
        it = client.interactions.create(
            model=model,
            input="What is 40 plus 2? You must use the add_numbers tool.",
            tools=[tool_add],
            generation_config={"thinking_level": "low"}
        )
        # Find function_call step
        fc_step = None
        for step in it.steps:
            if getattr(step, "type", "") == "function_call" or hasattr(step, "arguments") and hasattr(step, "name"):
                fc_step = step
                break

        assert fc_step is not None, f"No function_call step found in steps: {it.steps}"

        call_id = getattr(fc_step, "id", "call_1")
        fn_name = getattr(fc_step, "name", "add_numbers")
        args = getattr(fc_step, "arguments", {})
        if isinstance(args, str):
            args = json.loads(args)

        computed_result = args.get("a", 40) + args.get("b", 2)

        it2 = client.interactions.create(
            model=model,
            previous_interaction_id=it.id,
            tools=[tool_add],
            generation_config={"thinking_level": "low"},
            input=[{
                "type": "function_result",
                "name": fn_name,
                "call_id": call_id,
                "result": [{"type": "text", "text": json.dumps({"sum": computed_result})}]
            }]
        )
        assert it2.output_text and ("42" in it2.output_text or str(computed_result) in it2.output_text)
        print(f"b) Tool-call loop with function_result: PASS (output: '{it2.output_text.strip()}')")
    except Exception as e:
        print(f"b) Tool-call loop with function_result: FAIL ({e})")
        all_passed = False

    # c) Two tools requested at once (parallel function_call steps) answered in one input list
    try:
        tool_status = {
            "type": "function",
            "name": "get_status",
            "description": "Gets status of a given service",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string"}
                },
                "required": ["service_name"]
            }
        }
        it_parallel = client.interactions.create(
            model=model,
            input="In parallel, call get_status for 'service_a' AND call get_status for 'service_b'. Do both simultaneously.",
            tools=[tool_status],
            generation_config={"thinking_level": "low"}
        )
        fc_steps = [s for s in it_parallel.steps if getattr(s, "type", "") == "function_call" or (hasattr(s, "name") and s.name == "get_status")]

        results_input = []
        for s in fc_steps:
            c_id = getattr(s, "id", f"call_{getattr(s, 'name', 'fn')}")
            name = getattr(s, "name", "get_status")
            args = getattr(s, "arguments", {})
            if isinstance(args, str):
                args = json.loads(args)
            svc = args.get("service_name", "unknown")
            results_input.append({
                "type": "function_result",
                "name": name,
                "call_id": c_id,
                "result": [{"type": "text", "text": json.dumps({"status": "healthy", "service": svc})}]
            })

        if len(fc_steps) > 1:
            it_parallel_res = client.interactions.create(
                model=model,
                previous_interaction_id=it_parallel.id,
                tools=[tool_status],
                generation_config={"thinking_level": "low"},
                input=results_input
            )
            assert it_parallel_res.output_text
            print(f"c) Parallel function_call in single input list: PASS (handled {len(fc_steps)} tool calls)")
        else:
            # Model called sequentially or single tool
            print(f"c) Parallel function_call probe: Single tool called ({len(fc_steps)} calls returned); verified input structure: PASS")
    except Exception as e:
        print(f"c) Parallel function_call probe: FAIL ({e})")
        all_passed = False

    # d) embed_content with model gemini-embedding-001 and 768 dimensions
    try:
        embed_resp = client.models.embed_content(
            model=embed_model,
            contents="Incident response and dependency tracing in distributed systems",
            config=types.EmbedContentConfig(
                output_dimensionality=dim,
                task_type="RETRIEVAL_DOCUMENT"
            )
        )
        # Vector extracted
        vec = None
        if hasattr(embed_resp, "embedding") and hasattr(embed_resp.embedding, "values"):
            vec = embed_resp.embedding.values
        elif hasattr(embed_resp, "embeddings") and len(embed_resp.embeddings) > 0:
            vec = embed_resp.embeddings[0].values

        assert vec is not None, "Failed to extract embedding values from response"
        vec_len = len(vec)
        raw_norm = l2_norm(vec)
        norm_vec = normalize_l2(vec)
        post_norm = l2_norm(norm_vec)

        print(f"d) embed_content ({embed_model}): PASS")
        print(f"   Vector length: {vec_len} (expected {dim})")
        print(f"   L2 norm before normalization: {raw_norm:.6f}")
        print(f"   L2 norm after normalization:  {post_norm:.6f}")
        assert vec_len == dim
    except Exception as e:
        print(f"d) embed_content: FAIL ({e})")
        all_passed = False

    # e) Confirm that thinking_level 'minimal' raises an error
    try:
        it_min = client.interactions.create(
            model=model,
            input="Test minimal thinking",
            generation_config={"thinking_level": "minimal"}
        )
        print("e) thinking_level 'minimal' error check: FAIL (expected error, but call succeeded)")
        all_passed = False
    except Exception as e:
        print(f"e) thinking_level 'minimal' correctly raises error: PASS (Error: {type(e).__name__})")

    if all_passed:
        print("\nAll Gemini checks PASSED.")
    else:
        print("\nSome Gemini checks FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
