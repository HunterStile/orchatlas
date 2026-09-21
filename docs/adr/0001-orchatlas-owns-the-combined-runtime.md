# OrchAtlas owns the combined runtime

The intended product is a standalone application that coordinates Codex and OpenCode together. Codex uses the user's ChatGPT subscription for Astra planning and review; OpenCode uses OpenRouter credentials to run DeepSeek V4.1 Flash for implementation. OrchAtlas owns process lifecycle, handoffs, saved progress and acceptance, so the primary path does not route DeepSeek through Codex or require OpenAI authentication in OpenCode.

The existing configuration exports remain optional compatibility tools. The combined runtime ships in v0.2.0 after the maintainer authorized its release; future releases also require that authorization.
