"""
Skills System (Progressive Disclosure Architecture)
Provides on-demand knowledge injection for advanced domains.
"""

SKILLS_REGISTRY = {
    "software_engineering": """
[SKILL: SOFTWARE ENGINEERING & ARCHITECTURE]
- Write clean, modular, production-ready code with complete error handling.
- Support Python, Node.js, TypeScript, Go, Rust, C++, PHP, SQL, Docker, Shell.
- Implement async I/O, robust logging, security best practices, and clean project trees.
""",
    "web_research": """
[SKILL: DEEP WEB RESEARCH & SYNTHESIS]
- Cross-reference multi-source information from web_search and fetch_url.
- Provide objective summaries with dates, sources, and verified facts.
""",
    "media_art": """
[SKILL: VISUAL PROMPT ENGINEERING & DESIGN]
- Convert visual requests into detailed 8K photorealistic Flux prompts.
- Include cinematic lighting, camera lenses (e.g. 85mm f/1.4), volumetric atmosphere, and octane render aesthetic.
""",
    "security_analysis": """
[SKILL: REVERSE ENGINEERING & SECURITY]
- Analyze source code for vulnerabilities, logic flaws, and secure authentication.
- Write penetration testing scripts, fuzzers, and network automation for educational verification.
"""
}

def get_injected_skills():
    return "\n".join(SKILLS_REGISTRY.values())
