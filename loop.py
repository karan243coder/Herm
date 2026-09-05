import json
import re
import logging
from agent.soul import DEFAULT_SOUL_MD
from skills.manager import get_injected_skills
from memory.store import get_custom_identity, get_all_facts, fetch_history, add_history
from tools.registry import (
    TOOL_DEFINITIONS, exec_python_code, exec_pip_install, exec_web_search, exec_fetch_url,
    exec_crypto, exec_weather, exec_kanban, save_fact, add_cron_job
)

logger = logging.getLogger(__name__)

def build_full_system_prompt(chat_id: int) -> str:
    custom_identity = get_custom_identity(chat_id)
    facts = get_all_facts(chat_id)
    
    prompt = DEFAULT_SOUL_MD + "\n\n" + TOOL_DEFINITIONS + "\n\n" + get_injected_skills()
    if custom_identity:
        prompt += f"\n\n### USER PERSONA DIRECTIVE:\n{custom_identity}"
    if facts:
        prompt += "\n\n### REMEMBERED FACTS:\n" + "\n".join([f"- {f[0]}: {f[1]}" for f in facts])
    return prompt

def execute_agentic_turn(chat_id: int, user_input: str, model_router) -> tuple[str, dict]:
    add_history(chat_id, "user", user_input)
    
    system_prompt = build_full_system_prompt(chat_id)
    history = fetch_history(chat_id, limit=12)
    messages = [{"role": "system", "content": system_prompt}] + history
    
    artifacts = {
        "images": [],
        "files": [],
        "qrs": [],
        "zips": []
    }
    
    final_text = ""
    max_steps = 4
    
    for step in range(max_steps):
        logger.info(f"Agent Loop Step {step+1} for chat {chat_id}")
        response_text = model_router.generate_completion(messages)
        
        if not response_text:
            final_text = "⚠️ Server busy hai. Kripya thodi der baad try karein."
            break

        tool_match = re.search(r'<tool_call>(.*?)</tool_call>', response_text, re.DOTALL)
        if not tool_match:
            img_tag = re.search(r'<generate_image>(.*?)</generate_image>', response_text, re.DOTALL)
            if img_tag:
                artifacts["images"].append(img_tag.group(1).strip())
                response_text = re.sub(r'<generate_image>.*?</generate_image>', '', response_text, flags=re.DOTALL).strip()
            final_text = response_text
            break

        raw_tool = tool_match.group(1).strip()
        try:
            tdata = json.loads(raw_tool)
            tname = tdata.get("name")
            targs = tdata.get("arguments", {})
        except Exception as err:
            logger.warning(f"Tool parse error: {err}")
            final_text = response_text
            break

        logger.info(f"Dispatching tool: {tname} -> {targs}")
        tool_res = ""

        if tname == "execute_code":
            tool_res = exec_python_code(targs.get("code", ""))
        elif tname == "install_package":
            pkg = targs.get("package", "")
            tool_res = exec_pip_install(pkg)
        elif tname == "web_search":
            tool_res = exec_web_search(targs.get("query", ""))
        elif tname == "fetch_url":
            tool_res = exec_fetch_url(targs.get("url", ""))
        elif tname == "generate_image":
            p = targs.get("prompt", "")
            artifacts["images"].append(p)
            tool_res = f"Image queued for rendering: {p}"
        elif tname == "get_crypto_price":
            tool_res = exec_crypto(targs.get("coin", "bitcoin"))
        elif tname == "get_weather":
            tool_res = exec_weather(targs.get("city", "Delhi"))
        elif tname == "generate_qr":
            qdata = targs.get("data", "")
            artifacts["qrs"].append(qdata)
            tool_res = f"QR code generated: {qdata}"
        elif tname == "export_file":
            fn = targs.get("filename", "code.py")
            fc = targs.get("content", "")
            artifacts["files"].append({"filename": fn, "content": fc})
            tool_res = f"File '{fn}' ready for export."
        elif tname == "create_project_zip":
            zn = targs.get("zip_name", "project.zip")
            zf = targs.get("files", {})
            artifacts["zips"].append({"zip_name": zn, "files": zf})
            tool_res = f"Project ZIP '{zn}' generated."
        elif tname == "remember_fact":
            save_fact(chat_id, targs.get("key", "info"), targs.get("value", ""))
            tool_res = "Fact stored permanently."
        elif tname == "kanban_task":
            tool_res = exec_kanban(chat_id, targs.get("action", "list"), targs.get("task", ""))
        elif tname == "cron_schedule":
            task_d = targs.get("task", "Reminder")
            delay_m = int(targs.get("minutes", 10))
            tool_res = add_cron_job(chat_id, task_d, delay_m * 60)
        else:
            tool_res = f"Unknown tool: {tname}"

        messages.append({"role": "assistant", "content": response_text})
        messages.append({
            "role": "user",
            "content": f"<tool_response>\n{{\"name\": \"{tname}\", \"result\": {json.dumps(tool_res)}}}\n</tool_response>"
        })

    clean_out = re.sub(r'<thought>.*?</thought>', '', final_text, flags=re.DOTALL).strip()
    clean_out = re.sub(r'<tool_call>.*?</tool_call>', '', clean_out, flags=re.DOTALL).strip()
    if not clean_out:
        clean_out = final_text

    add_history(chat_id, "assistant", clean_out)
    return clean_out, artifacts
