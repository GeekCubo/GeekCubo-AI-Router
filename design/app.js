/* ==========================================================================
   GeekCubo — dashboard
   Vanilla JS, no build step. State -> render. Keyboard-first DX.
   ========================================================================== */

// A pre-2.0 dashboard kept an API key in localStorage. Kept only so the boot
// sequence can purge a stale value from an upgraded browser — the console never
// reads it as a credential any more.
const LEGACY_KEY_STORAGE = "geekcubo-api-key";
const ONBOARDING_KEY = "geekcubo-getting-started-dismissed";
const LOCALE_KEY = "geekcubo-locale";
const SUPPORTED_LOCALES = ["en", "zh", "hi", "es", "pt", "ru", "ja", "de", "fr", "it", "ar", "ko"];
const LOCALE_LABELS = { en: "English", zh: "中文", hi: "हिन्दी", es: "Español", pt: "Português", ru: "Русский", ja: "日本語", de: "Deutsch", fr: "Français", it: "Italiano", ar: "العربية", ko: "한국어" };
const I18N = {
  en: { "q.tabs_label":"Quality sections", "q.tab_models":"Models", "q.tab_scores":"Quality scores", "q.tab_aa":"Artificial Analysis", "q.col_availability":"Availability", "q.avail_yes":"available", "q.avail_no":"no provider key", "q.avail_no_title":"No configured provider key serves this model. Benchmark data alone does not make a model deployable.", "q.sync_title":"Benchmark synchronization", "q.sync_last_ok":"Last successful sync", "q.sync_last_attempt":"Latest attempt", "q.sync_returned":"Models returned by AA", "q.sync_matched":"Matched to catalog", "q.sync_unmatched":"Unmatched", "q.sync_overrides":"Manual overrides", "q.sync_outcome_ok":"succeeded", "q.sync_outcome_failed":"failed", "q.sync_need_key":"Add an Artificial Analysis key on the Artificial Analysis tab to synchronize benchmark scores. Manual overrides work without one.", "q.sync_never":"No synchronization has run with this key yet. Use Refresh from AA.", "q.sync_no_models":"The last synchronization returned no models.", "q.status_line":"{matched} models with benchmark data · {overrides} manual overrides", "q.src.live":"live", "q.src.stale_cache":"cached (AA unreachable)", "q.src.stale_db":"cached (saved snapshot)", "q.src.error":"sync failed", "q.src.missing_key":"no API key", "q.auto_status":"Auto-routing status", "q.auto_status_hint":"What model=\"auto\" would pick right now. This depends on configured providers, not on benchmark sync.", "q.auto_no_provider":"No deployable model satisfies the current requirements. Add a provider key on the Providers page. This is separate from Artificial Analysis synchronization.", "qa.credential":"API key", "qa.cred_stored":"Stored on this server (encrypted)", "qa.cred_env":"From the server environment", "qa.last_test":"Last connection test", "qa.last_test_ok":"Last successful test", "qa.not_tested":"Not tested yet", "qa.sync_status":"Benchmark sync", "qa.tier":"{tier} tier", "qa.troubleshooting":"Connection troubleshooting", "qa.status.key_configured":"Key configured", "qa.sync.not_configured":"Not configured", "qa.sync.never_synced":"Never synced", "qa.sync.synced":"Synced", "qa.sync.sync_failed":"Sync failed", "qa.err.invalid_key":"Invalid key", "qa.err.insufficient_tier":"Plan doesn't include endpoint", "qa.err.endpoint_retired":"Endpoint retired", "qa.err.rate_limited":"Rate limited", "qa.err.timeout":"Timed out", "qa.err.malformed_response":"Unexpected response", "qa.err.no_data":"No models returned", "qa.err.no_catalog_match":"No catalog matches", "qa.err.server_error":"AA server error", "qa.err.connection_failed":"Connection failed", "auth.tagline":"One Gateway. Every AI Model.", "auth.welcome":"Welcome back", "auth.subtitle":"Sign in to the administrator console for this GeekCubo installation.", "auth.api_key":"API key", "auth.continue":"Continue", "nav.search":"Search", "nav.overview":"Overview", "nav.providers":"Providers", "nav.routing":"Routing", "nav.analytics":"Analytics", "nav.api_keys":"API keys", "nav.help_docs":"Help & docs", "nav.sign_out":"Sign out", "status.connected":"Connected", "status.disconnected":"Disconnected", "auth.checking":"Checking…", "auth.welcome_aboard":"Welcome aboard.", "auth.key_invalid":"That key didn't work. Double-check the prefix sk-geek-…", "tab.overview.title":"Overview", "tab.overview.sub":"Your single-tenant LLM router at a glance.", "tab.providers.title":"Provider keys", "tab.providers.sub":"BYOK — encrypted at rest, used to call upstream LLMs.", "tab.routing.title":"Routing", "tab.routing.sub":"How model='auto' picks the right model for each request.", "tab.analytics.title":"Analytics", "tab.analytics.sub":"Local-only spend, latency and request history.", "tab.keys.title":"API keys", "tab.keys.sub":"sk-geek-* keys that authenticate SDK and CLI inference traffic.", "nav.quality":"Quality", "tab.quality.title":"Quality scores", "tab.quality.sub":"Real benchmark scores for the quality routing strategy. Pulls from Artificial Analysis.", "auth.username":"Username", "auth.password":"Password", "auth.sign_in":"Sign In", "nav.security":"Security", "tab.security.title":"Security", "tab.security.sub":"Administrator account, password and sessions.", "tab.profiles.title":"Routing profiles", "tab.profiles.sub":"Named Auto configurations clients select by model id.", "tab.integrations.title":"Connect a tool", "tab.integrations.sub":"Ready-to-use configuration for OpenCode, Claude Code, Cursor and more.", "tab.intelligence.title":"Model data", "tab.intelligence.sub":"Where model prices and limits come from.", "auth.loading":"Loading…", "auth.checking_status":"Checking administrator status.", "auth.signin_title":"Sign in", "auth.signin_sub":"Administrator access to this GeekCubo installation.", "auth.forgot":"Forgot your password?", "auth.reset_hint":"Reset it on the host or container:", "auth.reset_note":"Keys, providers and usage are unaffected.", "auth.setup_title":"Create administrator account", "auth.setup_sub":"Controls this GeekCubo installation: provider credentials, API keys and routing.", "auth.min_password":"Minimum 8 characters", "auth.confirm_password":"Confirm password", "auth.setup_token":"Setup token", "auth.from_log":"From the server log", "auth.create_admin":"Create Administrator", "auth.where_token":"Where is the setup token?", "auth.token_hint":"Printed in the server log on first start. To issue a new one:", "auth.toggle_password":"Show or hide password", "ov.spend":"Spend (7d)", "ov.savings":"Routing savings", "ov.p50":"p50 latency", "ov.models":"Models deployable", "ov.quickstart":"Quick start", "ov.recent":"Recent activity", "prov.title":"Provider keys", "prov.tab_std":"Standard Providers", "prov.tab_custom":"Custom Providers", "routing.strategy":"Routing strategy", "routing.pools":"Model pools", "routing.advanced":"Fallback, escalation & continuity", "routing.explain":"Test a routing decision", "profiles.title":"Routing profiles", "int.title":"Connect your AI tool", "md.title":"Model data sources", "md.lookup":"Price lookup", "an.spend":"Spend by model", "an.latency":"Latency by provider", "an.recent":"Recent requests", "keys.title":"Router API keys", "sec.sessions":"Sessions", "q.setup":"Set up quality scoring", "q.models":"Models", "preset.heading":"Start with a preset", "preset.sub":"Templates open the editor pre-filled — adjust anything before saving.", "preset.economy":"Cheapest capable model for each request. Lowest spend, no quality floor.", "preset.premium":"Strongest models first, price ignored. Best for work where quality dominates.", "preset.coding":"Tool calls and long prompts route to the Hard pool. For agent and editor work.", "preset.fast":"Balanced routing that prefers lower latency across the pool.", "ui.profiles":"Profiles", "ui.security":"Security", "ui.api_keys":"API Keys", "ui.connect_a_tool":"Connect a tool", "ui.model_data":"Model data", "ui.connecting":"Connecting…", "ui.language":"Language", "ui.light":"Light", "ui.system":"System", "ui.dark":"Dark", "ui.openai_compatible_base_url":"OpenAI-compatible base URL", "ui.copy":"Copy", "ui.use_this_in_any_openai_compatible_client":"Use this in any OpenAI-compatible client.", "ui.signed_in":"Signed in", "ui.security_and_sessions":"Security & sessions", "ui.api_keys_2":"API keys", "ui.sign_out":"Sign out", "ui.you_re_up_point_any_openai_sdk_at_your_b":"You're up — point any OpenAI SDK at your base URL.", "ui.last_5_requests_routed_through_this_serv":"Last 5 requests routed through this server.", "ui.view_all":"View all", "ui.no_requests_yet":"No requests yet.", "ui.new_here_get_fully_set_up_in_2_minutes":"New here? Get fully set up in 2 minutes", "ui.re_enter_as_a_named_provider":"Re-enter as a named provider", "ui.remove_legacy_entry":"Remove legacy entry", "ui.provider":"Provider", "ui.others_openai_format":"Others (OpenAI format)", "ui.api_key":"API key", "ui.provider_name":"Provider Name", "ui.display_name_a_unique_internal_slug_is_d":"Display name. A unique internal slug is derived from it automatically.", "ui.api_base_url":"API Base URL", "ui.usually_ends_in_v1_must_be_https_unless_":"Usually ends in /v1. Must be https unless the host is in CUSTOM_PROVIDER_ALLOWED_LOCAL_HOSTS.", "ui.api_key_2":"API Key", "ui.encrypted_at_rest_never_displayed_again_":"Encrypted at rest. Never displayed again after saving.", "ui.prefix":"Prefix", "ui.status":"Status", "ui.no_provider_keys_yet":"No provider keys yet", "ui.add_at_least_one_to_start_routing_real_t":"Add at least one to start routing real traffic. Pick a provider above or click a quick-add chip.", "ui.lowest_cost_that_clears_your_quality_flo":"Lowest cost that clears your quality floor. Safe default with any number of providers.", "ui.recommended":"Recommended", "ui.lowest_per_token_cost_meeting_the_reques":"Lowest per-token cost meeting the request's capabilities. Output quality may vary.", "ui.highest_score_from_artificial_analysis_o":"Highest score from Artificial Analysis or your manual overrides. Without scores it falls back to price as a proxy.", "ui.re_ranks_by_observed_success_rate_and_la":"Re-ranks by observed success rate and latency once each model has 20+ requests here. Until then: Balanced.", "ui.sends_each_request_to_your_mundane_or_ha":"Sends each request to your Mundane or Hard pool based on observable signals (tools, size, length).", "ui.highest_throughput_and_lowest_first_toke":"Highest throughput and lowest first-token latency from benchmark data. Kept for existing configs.", "ui.legacy":"Legacy", "ui.registered_models":"Registered models", "ui.show":"Show", "ui.deployable":"Deployable", "ui.custom_providers":"Custom providers", "ui.model":"Model", "ui.capabilities":"Capabilities", "ui.context":"Context", "ui.price_1m_in_out":"Price /1M (in · out)", "ui.availability":"Availability", "ui.pools":"Pools", "ui.previous":"Previous", "ui.next":"Next", "ui.fallback_and_escalation_always_keep_the_":"Fallback and escalation always keep the request's required capabilities. Decisions are made before a request starts; models never change mid-stream.", "ui.maximum_attempts_primary_fallbacks":"Maximum attempts (primary + fallbacks)", "ui.what_counts_as_retryable":"What counts as retryable", "ui.quality_floor_percentile_0_off":"Quality floor (percentile, 0 = off)", "ui.needs_quality_scores_ignored_and_reporte":"Needs quality scores; ignored (and reported) when none exist.", "ui.what_the_quality_floor_does":"What the quality floor does", "ui.balanced_weighs_price_against_quality_th":"Balanced weighs price against quality. The floor excludes models below that percentile, so a very cheap but weak model cannot win. Set it to 0 to disable the floor entirely.", "ui.messages":"Messages ≥", "ui.prompt_characters":"Prompt characters ≥", "ui.how_request_signals_are_measured":"How request signals are measured", "ui.mode":"Mode", "ui.off":"Off", "ui.manual_client_sends_x_geek_escalate":"Manual (client sends x-geek-escalate)", "ui.auto_after_repeated_upstream_failures":"Auto (after repeated upstream failures)", "ui.failures_before_escalating":"Failures before escalating", "ui.max_escalations_per_conversation":"Max escalations per conversation", "ui.destination_pool":"Destination pool", "ui.when_escalation_triggers":"When escalation triggers", "ui.remember_for_minutes":"Remember for (minutes)", "ui.what_continuity_does":"What continuity does", "ui.save_routing_policy":"Save routing policy", "ui.dry_run_shows_which_model_auto_would_cho":"Dry-run: shows which model Auto would choose and why. Nothing is sent upstream.", "ui.messages_2":"Messages", "ui.prompt_chars":"Prompt chars", "ui.explain":"Explain", "ui.three_filters_applied_in_order":"Three filters, applied in order.", "ui.how_each_strategy_maps_to_litellm_router":"How each strategy maps to LiteLLM Router", "ui.strategy":"Strategy", "ui.import_json":"Import JSON", "ui.new_profile":"New profile", "ui.generates_configuration_that_points_a_cl":"Generates configuration that points a client at this GeekCubo. Keys are referenced by environment variable, never embedded.", "ui.search_tools":"Search tools", "ui.routing_profile_or_model":"Routing profile or model", "ui.endpoint":"Endpoint", "ui.format":"Format", "ui.download":"Download", "ui.add_source":"Add source", "ui.name":"Name", "ui.https_url_models_dev_compatible_json":"HTTPS URL (models.dev-compatible JSON)", "ui.save_source":"Save source", "ui.cancel":"Cancel", "ui.shows_what_each_enabled_source_reports_f":"Shows what each enabled source reports for a model and which value GeekCubo would use. Your own configured prices always win.", "ui.look_up":"Look up", "ui.routing":"Routing", "ui.volume":"Volume", "ui.routing_decisions":"Routing decisions", "ui.how_auto_requests_were_classified_and_wh":"How Auto requests were classified and where they went.", "ui.by_tier":"By tier", "ui.by_strategy":"By strategy", "ui.by_routing_id":"By routing id", "ui.top_models_served":"Top models served", "ui.reliability":"Reliability", "ui.errors_by_cause":"Errors by cause", "ui.compare_against_a_baseline_model":"Compare against a baseline model", "ui.none":"None", "ui.compare":"Compare", "ui.how_the_comparison_is_calculated":"How the comparison is calculated", "ui.p50_and_p99_sourced_from_local_request_l":"p50 and p99 — sourced from local request logs.", "ui.requests":"Requests", "ui.newest_first_click_a_row_to_copy_its_tra":"Newest first. Click a row to copy its trace ID.", "ui.when":"When", "ui.tokens_in_out":"Tokens (in / out)", "ui.latency":"Latency", "ui.no_traffic_yet":"No traffic yet", "ui.once_you_start_sending_requests_they_ll_":"Once you start sending requests, they'll appear here in real time.", "ui.expires":"Expires", "ui.never":"Never", "ui.7_days":"7 days", "ui.30_days":"30 days", "ui.90_days":"90 days", "ui.1_year":"1 year", "ui.use_it_with_opencode":"Use it with OpenCode:", "ui.created":"Created", "ui.last_used":"Last used", "ui.actions":"Actions", "ui.no_api_keys":"No API keys", "ui.generate_one_above_to_start_sending_requ":"Generate one above to start sending requests from an SDK or CLI.", "ui.administrator":"Administrator", "ui.the_single_local_account_that_controls_t":"The single local account that controls this installation.", "ui.password_was_reset_from_the_command_line":"Password was reset from the command line", "ui.change_password":"Change password", "ui.current_password":"Current Password", "ui.new_password":"New Password", "ui.confirm_new_password":"Confirm New Password", "ui.update_password":"Update password", "ui.signed_in_browsers_for_this_administrato":"Signed-in browsers for this administrator. Sessions expire after 12 hours, or 60 minutes idle.", "ui.log_out_all_other_sessions":"Log out all other sessions", "ui.device":"Device", "ui.last_active":"Last active", "ui.local_recovery":"Local recovery", "ui.password_recovery_is_local_only_by_desig":"Password recovery is local-only by design — there is no email reset and no public endpoint that can change the password.", "ui.open_a_shell_where_geekcubo_runs_host_or":"Open a shell where GeekCubo runs (host or container).", "ui.choose_a_new_password_at_the_prompt_all_":"Choose a new password at the prompt. All dashboard sessions are signed out; API keys, providers and usage data are untouched.", "ui.artificial_analysis_api_key":"Artificial Analysis API key", "ui.optional":"(optional)", "ui.save_key":"Save key", "ui.remove_stored_key":"Remove stored key", "ui.how_quality_scoring_works":"How quality scoring works", "ui.paste_it_above_and_save_it_is_encrypted_":"Paste it above and save. It is encrypted at rest, and anything already cached is discarded so the next refresh uses the new key.", "ui.quality_scores":"Quality scores", "ui.where_these_numbers_come_from":"Where these numbers come from", "ui.manual":"Manual", "ui.effective":"Effective", "ui.m_blended":"$/M blended", "ui.help_and_docs":"Help & docs", "ui.what_is_geekcubo":"What is GeekCubo?", "ui.60_second_quickstart":"60-second quickstart", "ui.keyboard_shortcuts":"Keyboard shortcuts", "ui.switch_tabs":"Switch tabs", "ui.command_palette":"Command palette", "ui.toggle_this_help":"Toggle this help", "ui.close_drawers_palette":"Close drawers / palette", "ui.going_further":"Going further", "js.ov_empty_a":"No requests yet.", "js.ov_empty_b":"Once you send your first call, it'll show up here.", "js.ra_unavailable":"Routing analytics unavailable.", "js.no_spend":"No spend recorded in this window yet.", "js.no_traffic":"No traffic yet", "toast.copied":"Copied to clipboard", "toast.copy_blocked":"Could not copy — your browser blocked it", "toast.signed_in":"Signed in as {name}", "toast.admin_created":"Administrator {name} created", "toast.signed_out":"Signed out", "toast.load_providers_failed":"Couldn't load providers: {msg}", "toast.removed_provider":"Removed {name}", "toast.api_key_empty":"API key cannot be empty", "toast.saved_provider":"Saved {name} key", "toast.load_custom_failed":"Couldn't load custom providers: {msg}", "toast.updated":"Updated {name}", "toast.model_id_empty":"Model ID cannot be empty", "toast.model_id_dup":"That model ID is already registered", "toast.model_saved":"Model saved", "toast.select_one_model":"Select at least one new model", "toast.added_models_one":"Added 1 model", "toast.added_models_many":"Added {count} models", "toast.load_routing_failed":"Couldn't load routing: {msg}", "toast.routing_strategy":"Routing strategy: {name}", "toast.policy_saved":"Routing policy saved", "toast.load_models_failed":"Couldn't load models: {msg}", "toast.load_analytics_failed":"Couldn't load analytics: {msg}", "toast.load_keys_failed":"Couldn't load keys: {msg}", "toast.revoked":"Revoked {name}", "toast.name_empty":"Name cannot be empty", "toast.key_renamed":"Key renamed", "toast.name_first":"Give the key a name first", "toast.created":"Created {name}", "toast.load_security_failed":"Couldn't load security settings: {msg}", "toast.password_updated":"Password updated — other devices signed out", "toast.load_quality_failed":"Couldn't load quality scores: {msg}", "toast.score_range":"Score must be a number between 0 and 100", "toast.override_set":"Override set for {name}", "toast.reset":"Reset {name}", "toast.aa_saved":"Artificial Analysis key saved", "toast.stored_removed":"Stored key removed", "toast.remove_key_failed":"Couldn't remove the key: {msg}", "toast.aa_refreshed":"Refreshed scores from Artificial Analysis", "toast.refresh_failed":"Refresh failed: {msg}", "toast.load_profiles_failed":"Couldn't load profiles: {msg}", "toast.duplicated":"Duplicated {name}", "toast.now_default":"{name} is now the default", "toast.deleted":"Deleted {name}", "toast.default_reassigned":" — default is now auto", "toast.saved_profile":"Saved {name}", "toast.file_too_large":"That file is too large to be a profile export.", "toast.load_integrations_failed":"Couldn't load integration options: {msg}", "toast.load_mi_failed":"Couldn't load model data sources: {msg}", "toast.source_added":"Source added", "toast.legacy_removed":"Removed legacy \"__custom__\" entry", "toast.saved_as":"Saved {name} as {slug}. Fetch its models below.", "confirm.remove_provider":"Remove the {name} key? Requests routed to {name} will start failing.", "confirm.remove_model":"Remove model {name}?", "confirm.remove_custom":"Remove provider \"{name}\" and its models?", "confirm.sign_out_others":"Sign out every other browser signed in as this administrator?", "confirm.reset_score":"Reset {name} to its AA score?", "confirm.remove_aa_key":"Remove the stored Artificial Analysis key? An environment key, if set, takes over again.", "confirm.change_slug":"Change the API identifier from \"{old}\" to \"{new}\"?\n\nEvery client sending model: \"{old}\" will stop working.", "confirm.delete_source":"Delete this metadata source?", "confirm.legacy_remove":"Permanently remove the legacy \"__custom__\" provider key ({prefix})?\n\nIt is not used for routing. Make sure you have the key saved elsewhere if you still need it — it cannot be recovered.", "confirm.revoke":"Revoke \"{name}\"?\n\nClients using this key get 401 immediately. This cannot be undone — issue a new key if you need access again.", "confirm.rotate":"Rotate \"{name}\"?\n\nA replacement key with the same restrictions is created and shown once.\n\nOK = revoke the old key now (immediate cutover).\nCancel = keep the old key working until you revoke it yourself.", "prompt.rename_key":"Rename key \"{name}\" to:", "prompt.set_score":"Set manual quality score for {name} (0-100):", "prompt.aa_current":"AA score is currently: {score}", "prompt.override_note":"Optional note (why are you overriding?):", "auth.session_expired":"Your session expired. Sign in again.", "auth.enter_creds":"Enter your username and password.", "auth.creds_required":"Username and password are required.", "auth.pw_mismatch":"Passwords do not match.", "auth.paste_token":"Paste the one-time setup token from the server log.", "auth.signed_out":"Signed out.", "auth.pw_match":"Passwords match.", "auth.pw_mismatch_yet":"Passwords do not match yet.", "auth.new_pw_mismatch":"New passwords do not match.", "auth.fill_three":"Fill in all three fields.", "qa.connection":"Artificial Analysis connection", "qa.test":"Test connection", "qa.replace":"Replace key", "qa.add":"Add key", "qa.remove":"Remove key", "qa.last_sync":"Last successful sync", "qa.last_error":"Latest error", "qa.never":"never synced yet", "qa.from_env":"from environment", "qa.saving":"Saving…", "qa.key_hint":"Stored encrypted on this server and never shown again. The previous key stays active until this one is saved.", "qa.daily_limit_label":"Your key's daily limit", "qa.daily_limit_hint":"Requests per 24 hours, as shown on your Artificial Analysis account page. Leave blank to use the documented 100 / day.", "qa.status.not_configured":"Not configured", "qa.status.connected":"Connected", "qa.status.invalid_key":"Invalid key", "qa.status.rate_limited":"Rate limited", "qa.status.connection_failed":"Connection failed", "qa.status.cached":"Cached data", "pricing.legend":"Pricing", "pricing.allow_estimates":"Allow reference estimates in Auto, Cheapest and cost ceilings", "pricing.allow_estimates_help":"Off by default. Only confirmed provider prices are compared; models with only a reference estimate stay out of Auto. When on, every estimate-based decision is labelled.", "confirm.bulk_remove_models":"Remove {count} selected model{plural}? Pinned requests to them will fail.", "nav.chat":"Chat", "tab.chat.title":"Chat", "tab.chat.sub":"Talk to your deployed models. Routed, cached and metered like SDK traffic.", "ui.open_chat":"Open chat", "ui.open_chat_hint":"Chat with your deployed models from the browser — same routing, caching and cost tracking as SDK traffic.", "chat.new":"New chat", "chat.settings_title":"Chat settings", "chat.default_title":"New chat", "chat.clear_history":"Clear history…", "chat.conversations_aria":"Conversations", "chat.model_aria":"Model", "chat.regenerate":"Regenerate reply", "chat.empty_title":"Ask anything.", "chat.empty_sub":"Requests route through the engine — the same routing, caching and cost tracking as SDK traffic.", "chat.input_placeholder":"Message GeekCubo…", "chat.send":"Send", "chat.stop":"Stop", "chat.system_prompt":"System prompt…", "chat.system_prompt_set":"System prompt ✓", "chat.system_ph":"You are a helpful assistant…", "chat.system_help":"Blank = use the chat default. Saved per conversation.", "chat.save_prompt":"Save prompt", "chat.default_model":"Default model", "chat.default_model_help":"Used for new conversations. The conversation's own picker overrides it.", "chat.temperature":"Temperature", "chat.max_tokens":"Max output tokens", "chat.default_system_prompt":"Default system prompt", "chat.default_system_prompt_ph":"You are a concise engineering assistant.", "chat.default_system_help":"Applies to conversations without their own prompt.", "chat.save_history":"Save chat history on this server", "chat.retention_days":"Keep conversations for (days)", "chat.retention_help":"Older conversations are pruned. Blank keeps everything.", "chat.font_size":"Message text size", "chat.fs_small":"Small", "chat.fs_medium":"Medium", "chat.fs_large":"Large", "chat.enter_to_send":"Enter sends the message", "chat.privacy_note":"Conversations stay on this server's database. Requests are sent to the providers you configured, exactly like SDK traffic.", "chat.privacy_ack":"I understand chat traffic goes to configured providers", "chat.save_settings":"Save settings", "chat.model_auto":"Auto (router picks)", "chat.no_conversations":"No conversations yet.", "chat.delete_convo_title":"Delete this conversation", "chat.kbd_enter_send":"Enter to send · Shift+Enter for a newline", "chat.kbd_ctrl_enter_send":"Ctrl+Enter to send · Enter for a newline", "chat.tokens_meta":"{in} in · {out} out", "chat.error_note":"Generation stopped before completion.", "chat.upstream_error":"The upstream model returned an error.", "toast.chat_load_failed":"Could not load chat data: {msg}", "toast.chat_failed":"Chat request failed: {msg}", "toast.chat_convo_deleted":"Conversation deleted", "toast.chat_cleared":"Cleared {count} conversation{plural}", "toast.chat_temp_range":"Temperature must be between 0 and 2", "toast.chat_settings_saved":"Chat settings saved", "toast.chat_open_convo":"Open a conversation first", "toast.chat_saved_prompt":"System prompt saved for this conversation", "confirm.delete_conversation":"Delete this conversation?\n\nMessages are removed from the server's database. Usage and cost records stay in analytics.", "confirm.clear_chat_history":"Delete ALL saved conversations?\n\nEvery chat message stored on this server is removed. Usage and cost records stay in analytics.", "q.ov_score":"Manual score (0–100)", "q.ov_note":"Note", "q.ov_model_ph":"openai/gpt-4o, anthropic/claude-…", "q.ov_note_ph":"Why this overrides the AA score", "q.ov_apply":"Apply override", "q.ov_clear":"Clear override", "q.ov_help":"One or more model ids, comma-separated — the override applies to every listed model. Manual scores always win over AA scores.", "toast.q_ids_required":"Enter at least one model id", "toast.q_too_many":"Bulk is limited to 500 model ids", "toast.q_bulk_set":"Override set for {count} model(s)", "toast.q_bulk_clear":"Overrides cleared for {count} model(s)", "providers.bulk_actions":"Bulk model actions", "providers.select_all":"Select all", "providers.selected_count":"{count} selected", "providers.bulk_capability":"Capability", "providers.bulk_capability_state":"Capability state", "providers.cap_tools":"Tools", "providers.cap_vision":"Vision", "providers.cap_supported":"Supported", "providers.cap_unsupported":"Unsupported", "providers.cap_unknown":"Unknown", "providers.cap_catalog":"Use catalog", "providers.cap_json_mode":"JSON mode", "providers.cap_json_schema":"JSON schema", "providers.apply":"Apply", "providers.enable":"Enable", "providers.disable":"Disable", "providers.remove_selected":"Remove selected", "providers.resolve_metadata":"Resolve", "toast.metadata_resolved":"Metadata: {resolved} resolved, {ambiguous} ambiguous, {unmatched} unmatched, {failed} failed.", "select.search_ph":"Search catalog keys…", "providers.catalog_key_ph":"Search catalog keys…", "select.remove_item":"Remove {name}", "select.use_custom":"Use \"{name}\"", "select.no_matches":"No matching models", "select.more_results":"{count} more — keep typing to narrow", "q.ov_model_search_ph":"Search and pick models…", "q.ov_help_picker":"Search and pick one or more models, or tick rows in the table below. Manual scores always win over AA scores.", "q.filter_ph":"Filter models…", "q.select_filtered":"Select filtered", "q.select_all_filtered":"Select all filtered models", "q.deselect_all":"Deselect all", "q.bulk_set":"Set score for selected", "q.bulk_clear":"Clear selected overrides", "q.select_model":"Select {name}", "confirm.q_bulk_clear":"Clear manual overrides for {count} selected models?", "qa.daily_limit_short":"Daily limit", "chat.attach":"Attach files", "chat.attach_drop":"Drop files to attach", "chat.attach_remove":"Remove attachment", "chat.attach_unreadable":"This file could not be read; only its name is sent.", "chat.attach_uploading":"Uploading…", "chat.attach_too_large":"Too large (max {max} MB)", "toast.chat_attach_failed":"Could not attach {name}: {msg}", "toast.chat_attach_disabled":"Attachments are disabled on this server.", "toast.chat_attach_too_many":"At most {max} attachments per message.", "toast.chat_attach_extract_failed":"{name}: could not be read ({msg})", "toast.chat_attach_wait":"Wait for uploads to finish.", "chat.search_toggle":"Web search", "chat.search_settings":"Web search", "chat.search_help":"When enabled, GeekCubo searches the web before answering and cites the pages it used. Results are injected as a system message, so any model can use them.", "chat.search_mode":"Search mode", "chat.search_mode_off":"Off", "chat.search_mode_manual":"Manual (per message)", "chat.search_mode_auto":"Auto (reserved)", "chat.search_mode_help":"Manual shows a toggle in the composer. Auto is reserved and not implemented yet.", "chat.search_backend":"Search backend", "chat.search_backend_none":"Choose a backend…", "chat.search_backend_searxng":"SearXNG (self-hosted)", "chat.search_backend_brave":"Brave Search API", "chat.search_backend_tavily":"Tavily", "chat.search_url":"SearXNG URL", "chat.search_url_ph":"http://searxng:8080/", "chat.search_url_help":"Base URL of your SearXNG instance. The installer's search profile serves this on the internal network.", "chat.search_api_key":"API key", "chat.search_api_key_ph":"Paste a new key to replace the saved one", "chat.search_key_clear":"Remove saved key", "chat.search_key_help":"Stored encrypted on this server and never shown again. Brave and Tavily require a key; SearXNG does not.", "chat.search_max_searches":"Max searches per conversation", "chat.search_max_results":"Results per search", "chat.search_max_fetches":"Pages to fetch per search", "chat.search_timeout":"Search timeout (seconds)", "chat.search_test":"Test connection", "chat.search_testing":"Testing…", "chat.search_test_ok":"{count} results in {ms} ms", "chat.search_test_failed":"Search test failed: {msg}", "chat.search_key_state_unset":"No key saved", "chat.search_key_state_set":"Key saved", "chat.search_key_state_undecryptable":"Saved key cannot be decrypted", "chat.context_budget":"Context: {tokens} / {budget} tokens", "chat.context_omitted":"{count} earlier messages omitted", "chat.sources":"Sources", "chat.search_used":"web search: {backend}", "toast.search_saved":"Web search settings saved", "toast.search_save_failed":"Couldn't save web search settings: {msg}", "toast.search_test_failed":"Web search test failed", "nav.local":"Local AI", "tab.local.title":"Local AI", "tab.local.sub":"Serve models from your own machines through this router.", "local.title":"Local AI Connect", "local.sub":"Route to models running on your own machines. A small connector dials out to this server, so no ports are opened and no inbound tunnel is needed.", "local.refresh":"Refresh", "local.setup_button":"Set up a machine", "local.feature_off_title":"Local AI Connect is turned off on the server", "local.feature_off_body":"Set LOCAL_CONNECT_ENABLED=true in the server environment and restart, then reload this page.", "local.url_missing_title":"No public URL configured", "local.url_missing_body":"Set LOCAL_CONNECT_PUBLIC_URL to the address connectors should dial (for example https://example.com) so the install command and service files are filled in.", "local.settings_title":"Routing behaviour", "local.settings_sub":"Controls whether local models take part in Auto and whether a request may fall back to the cloud.", "local.set_enabled":"Enable local machines for routing", "local.set_auto":"Include local models in Auto selection", "local.set_no_fallback":"Never fall back to the cloud when a local model fails", "local.settings_help":"Local models are only considered for Auto when they have a confirmed price of zero and the machine is approved and online. With \"never fall back\" on, a local-only request fails rather than being served by a cloud provider.", "local.save_settings":"Save", "local.settings_saved":"Local routing settings saved.", "local.machines_title":"Machines", "local.machines_sub":"Each machine is one connector. Pending machines are visible but are not routed to until you approve them.", "local.machines_empty":"No machines yet. Use \"Set up a machine\" to generate an enrollment code.", "local.enrollments_title":"Enrollment codes", "local.enrollments_sub":"One-time codes that let a connector register. Each code is consumed the first time a machine connects.", "local.new_code":"New code", "local.install_title":"Install the connector", "local.install_sub":"Run this on the machine that hosts your models (Ollama, LM Studio, vLLM, llama.cpp or any [OI]-compatible server).", "local.service_files":"Run it as a service", "local.delete":"Delete", "local.never":"never", "local.ctx_suffix":"context", "local.ctx_unknown":"context unknown", "local.no_models":"This machine has not reported any models yet.", "local.no_enrollments":"No enrollment codes.", "local.enroll_active":"Active", "local.enroll_used":"Used", "local.status_online":"Online", "local.status_offline":"Offline", "local.status_pending":"Pending approval", "local.status_approved":"Approved", "local.status_revoked":"Revoked", "local.pending_note":"This machine is waiting for approval. Models are listed but will not be routed to.", "local.action_approve":"Approve", "local.action_discover":"Discover models", "local.action_revoke":"Revoke", "local.action_rotate":"Rotate credential", "local.action_delete":"Delete", "local.meta_host":"Hostname", "local.meta_platform":"Platform", "local.meta_agent":"Connector version", "local.meta_adapters":"Adapters", "local.meta_seen":"Last seen", "local.col_model":"Model", "local.col_adapter":"Adapter type", "local.col_context":"Context", "local.col_caps":"Capabilities", "local.col_enabled":"Enabled", "local.kpi_machines":"Machines", "local.kpi_online":"Online now", "local.kpi_pending":"Pending approval", "local.kpi_models":"Models", "local.toast_approved":"Machine approved.", "local.toast_revoked":"Machine revoked.", "local.toast_deleted":"Machine deleted.", "local.toast_discovered":"Model list refreshed.", "local.confirm_revoke":"Revoke this machine? Its connector is disconnected immediately and cannot reconnect until you rotate its credential.", "local.confirm_delete_machine":"Delete this machine and its model list? This cannot be undone.", "local.confirm_rotate":"Rotate this machine's credential? The running connector keeps working until it reconnects, then the old credential is rejected.", "local.confirm_delete_enrollment":"Delete this enrollment code?", "local.credential_once_title":"Copy the new credential now", "local.credential_once_body":"It is shown only once. Store it in the connector config on the machine.", "local.wizard_title":"Connect a local machine", "local.wizard_close":"Close", "local.wizard_back":"Back", "local.wizard_next":"Next", "local.wizard_done":"Done", "local.step1":"Enable", "local.step2":"Enrollment code", "local.step3":"Install", "local.step4":"Enroll", "local.step5":"Start", "local.step6":"Approve", "local.step7":"Models", "local.step8":"Auto routing", "local.w0_title":"Turn the feature on", "local.w0_body":"Local AI Connect is a server-side feature. It must be enabled before connectors can register.", "local.w0_ready":"The feature is enabled. Continue to create an enrollment code.", "local.w0_blocked":"The feature is disabled on this server. Set LOCAL_CONNECT_ENABLED=true and restart, then reload this page.", "local.w1_title":"Create an enrollment code", "local.w1_body":"A one-time code authorises a single connector to register. It expires after a short period.", "local.w1_name":"Machine name (optional)", "local.w1_name_ph":"e.g. office-gpu", "local.w1_name_help":"A label to recognise this machine in the list. You can rename it later.", "local.w1_created":"Enrollment code created", "local.w2_title":"Install the connector package", "local.w2_body":"On the machine that hosts your models, install the connector. Python 3.11 or newer is required.", "local.w2_note":"Install into a virtual environment to keep it isolated from system packages.", "local.w3_title":"Enroll the machine", "local.w3_body":"Run the enroll command with the code from step 2. The credential is written to the connector config file.", "local.w3_note":"The code is single-use. If it has expired, create a new one.", "local.w4_title":"Start the connector", "local.w4_body":"Run the connector in the foreground to watch it connect, then move it to a service.", "local.w4_note":"The connector keeps a single outbound WebSocket open and reconnects automatically.", "local.w5_title":"Wait for the machine to appear", "local.w5_body":"Once the connector connects, the machine shows up here. Refresh if it takes a moment.", "local.w5_seen":"{name} has connected.", "local.w5_waiting":"No machine has connected yet.", "local.w5_recheck":"Check again", "local.w6_title":"Approve the machine", "local.w6_body":"A new machine stays pending until an administrator approves it. Nothing is routed to it before then.", "local.w6_none":"There is no machine to approve yet.", "local.w6_must_approve":"Approve the pending machine before continuing.", "local.w7_title":"Enable local models in Auto", "local.w7_body":"Turn on \"Include local models in Auto selection\" and enable the models you want to route to. Local models are only chosen for Auto when their price is a confirmed zero.", "local.w7_done":"Setup is complete. Local models now appear in the Providers and Routing pages." },
  zh: { "q.tabs_label":"质量分区", "q.tab_models":"模型", "q.tab_scores":"质量评分", "q.tab_aa":"Artificial Analysis 连接", "q.col_availability":"可用性", "q.avail_yes":"可用", "q.avail_no":"无提供商密钥", "q.avail_no_title":"没有已配置的提供商密钥可服务此模型。仅有基准数据并不代表模型可部署。", "q.sync_title":"基准数据同步", "q.sync_last_ok":"最近一次成功同步", "q.sync_last_attempt":"最近一次尝试", "q.sync_returned":"AA 返回的模型数", "q.sync_matched":"匹配到目录", "q.sync_unmatched":"未匹配", "q.sync_overrides":"手动覆盖", "q.sync_outcome_ok":"成功", "q.sync_outcome_failed":"失败", "q.sync_need_key":"请在 Artificial Analysis 标签页添加密钥以同步基准评分。手动覆盖无需密钥即可使用。", "q.sync_never":"此密钥尚未进行同步。请使用“从 AA 刷新”。", "q.sync_no_models":"上次同步未返回任何模型。", "q.status_line":"{matched} 个模型有基准数据 · {overrides} 个手动覆盖", "q.src.live":"实时", "q.src.stale_cache":"缓存（AA 无法访问）", "q.src.stale_db":"缓存（已保存快照）", "q.src.error":"同步失败", "q.src.missing_key":"无 API 密钥", "q.auto_status":"自动路由状态", "q.auto_status_hint":"model=\"auto\" 当前会选择的模型。这取决于已配置的提供商，与基准同步无关。", "q.auto_no_provider":"没有可部署的模型满足当前要求。请在“提供商”页面添加提供商密钥。这与 Artificial Analysis 同步无关。", "qa.credential":"API 密钥", "qa.cred_stored":"保存在此服务器（已加密）", "qa.cred_env":"来自服务器环境变量", "qa.last_test":"最近一次连接测试", "qa.last_test_ok":"最近一次成功测试", "qa.not_tested":"尚未测试", "qa.sync_status":"基准同步", "qa.tier":"{tier} 套餐", "qa.troubleshooting":"连接故障排查", "qa.status.key_configured":"已配置密钥", "qa.sync.not_configured":"未配置", "qa.sync.never_synced":"从未同步", "qa.sync.synced":"已同步", "qa.sync.sync_failed":"同步失败", "qa.err.invalid_key":"密钥无效", "qa.err.insufficient_tier":"套餐不包含此端点", "qa.err.endpoint_retired":"端点已停用", "qa.err.rate_limited":"已达速率限制", "qa.err.timeout":"超时", "qa.err.malformed_response":"响应格式异常", "qa.err.no_data":"未返回模型", "qa.err.no_catalog_match":"无目录匹配", "qa.err.server_error":"AA 服务器错误", "qa.err.connection_failed":"连接失败", "auth.tagline":"一个网关。所有 AI 模型。", "auth.welcome":"欢迎回来", "auth.subtitle":"登录此 GeekCubo 安装的管理员控制台。", "auth.api_key":"API 密钥", "auth.continue":"继续", "nav.search":"搜索", "nav.overview":"概览", "nav.providers":"供应商", "nav.routing":"路由", "nav.analytics":"分析", "nav.api_keys":"API 密钥", "nav.help_docs":"帮助与文档", "nav.sign_out":"退出登录", "status.connected":"已连接", "status.disconnected":"已断开", "auth.checking":"正在检查…", "auth.welcome_aboard":"欢迎使用。", "auth.key_invalid":"该密钥无效，请检查前缀 sk-geek-…", "tab.overview.title":"概览", "tab.overview.sub":"一览你的单租户 LLM 路由器。", "tab.providers.title":"供应商密钥", "tab.providers.sub":"BYOK — 静态加密存储，用于调用上游 LLM。", "tab.routing.title":"路由", "tab.routing.sub":"model='auto' 如何为每个请求选择合适模型。", "tab.analytics.title":"分析", "tab.analytics.sub":"仅本地的花费、延迟和请求历史。", "tab.keys.title":"API 密钥", "tab.keys.sub":"用于验证 SDK 与 CLI 推理请求的 sk-geek-* 密钥。", "nav.quality":"质量", "tab.quality.title":"质量分数", "tab.quality.sub":"真实 benchmark 分数驱动 quality 路由策略,数据来自 Artificial Analysis。", "auth.username":"用户名", "auth.password":"密码", "auth.sign_in":"登录", "nav.security":"安全", "tab.security.title":"安全", "tab.security.sub":"管理员账户、密码与会话。", "tab.profiles.title":"路由配置", "tab.profiles.sub":"客户端按模型 ID 选择的具名 Auto 配置。", "tab.integrations.title":"接入工具", "tab.integrations.sub":"为 OpenCode、Claude Code、Cursor 等工具生成可直接使用的配置。", "tab.intelligence.title":"模型数据", "tab.intelligence.sub":"模型价格与上下文上限的来源。", "auth.loading":"正在加载…", "auth.checking_status":"正在检查管理员状态。", "auth.signin_title":"登录", "auth.signin_sub":"管理员可访问此 GeekCubo 安装。", "auth.forgot":"忘记密码？", "auth.reset_hint":"在主机或容器上重置：", "auth.reset_note":"密钥、供应商与用量均不受影响。", "auth.setup_title":"创建管理员账户", "auth.setup_sub":"管理此 GeekCubo 安装：供应商凭据、API 密钥与路由。", "auth.min_password":"至少 8 个字符", "auth.confirm_password":"确认密码", "auth.setup_token":"安装令牌", "auth.from_log":"来自服务器日志", "auth.create_admin":"创建管理员", "auth.where_token":"安装令牌在哪里？", "auth.token_hint":"首次启动时打印在服务器日志中。如需重新签发：", "auth.toggle_password":"显示或隐藏密码", "ov.spend":"支出（7 天）", "ov.savings":"路由节省", "ov.p50":"p50 延迟", "ov.models":"可用模型", "ov.quickstart":"快速开始", "ov.recent":"最近活动", "prov.title":"供应商密钥", "prov.tab_std":"标准供应商", "prov.tab_custom":"自定义供应商", "routing.strategy":"路由策略", "routing.pools":"模型池", "routing.advanced":"回退、升级与连续性", "routing.explain":"测试路由决策", "profiles.title":"路由配置", "int.title":"接入 AI 工具", "md.title":"模型数据源", "md.lookup":"价格查询", "an.spend":"按模型支出", "an.latency":"按供应商延迟", "an.recent":"最近请求", "keys.title":"路由器 API 密钥", "sec.sessions":"会话", "q.setup":"设置质量评分", "q.models":"模型", "preset.heading":"从预设开始", "preset.sub":"模板会预先填入编辑器内容，保存前可任意调整。", "preset.economy":"为每个请求选择最便宜且可用的模型，花费最低，不设质量下限。", "preset.premium":"优先最强模型，不考虑价格，适合质量至上的工作。", "preset.coding":"工具调用与长提示会进入 Hard 池，适合智能体与编辑器场景。", "preset.fast":"均衡路由，倾向于池中延迟更低的模型。", "ui.profiles":"配置", "ui.security":"安全", "ui.api_keys":"API 密钥", "ui.connect_a_tool":"接入工具", "ui.model_data":"模型数据", "ui.connecting":"正在连接…", "ui.language":"语言", "ui.light":"浅色", "ui.system":"跟随系统", "ui.dark":"深色", "ui.openai_compatible_base_url":"OpenAI 兼容基础 URL", "ui.copy":"复制", "ui.use_this_in_any_openai_compatible_client":"可用于任何 OpenAI 兼容客户端。", "ui.signed_in":"已登录", "ui.security_and_sessions":"安全与会话", "ui.api_keys_2":"API 密钥", "ui.sign_out":"退出登录", "ui.you_re_up_point_any_openai_sdk_at_your_b":"一切就绪 —— 把任意 OpenAI SDK 指向你的基础 URL。", "ui.last_5_requests_routed_through_this_serv":"本服务器最近 5 条请求的路由情况。", "ui.view_all":"查看全部", "ui.no_requests_yet":"暂无请求。", "ui.new_here_get_fully_set_up_in_2_minutes":"第一次使用？2 分钟完成全部配置", "ui.re_enter_as_a_named_provider":"重新作为具名供应商录入", "ui.remove_legacy_entry":"移除旧条目", "ui.provider":"供应商", "ui.others_openai_format":"其他（OpenAI 格式）", "ui.api_key":"API 密钥", "ui.provider_name":"供应商名称", "ui.display_name_a_unique_internal_slug_is_d":"显示名称。系统会自动生成唯一的内部标识。", "ui.api_base_url":"API 基础 URL", "ui.usually_ends_in_v1_must_be_https_unless_":"通常以 /v1 结尾。除非主机在 CUSTOM_PROVIDER_ALLOWED_LOCAL_HOSTS 中，否则必须是 https。", "ui.api_key_2":"API 密钥", "ui.encrypted_at_rest_never_displayed_again_":"静态加密存储，保存后不再显示。", "ui.prefix":"前缀", "ui.status":"状态", "ui.no_provider_keys_yet":"还没有供应商密钥", "ui.add_at_least_one_to_start_routing_real_t":"至少添加一个才能路由真实流量。可在上方选择供应商，或点击快速添加。", "ui.lowest_cost_that_clears_your_quality_flo":"在满足质量下限的前提下成本最低。无论供应商多少都安全可靠。", "ui.recommended":"推荐", "ui.lowest_per_token_cost_meeting_the_reques":"在满足请求能力要求的前提下每 token 成本最低。输出质量可能有差异。", "ui.highest_score_from_artificial_analysis_o":"取 Artificial Analysis 分数或你手动覆盖值中的最高者。没有分数时退化为以价格为近似。", "ui.re_ranks_by_observed_success_rate_and_la":"当每个模型在此累计 20+ 条请求后，按实测成功率和延迟重新排序。在此之前：均衡。", "ui.sends_each_request_to_your_mundane_or_ha":"根据可观测信号（工具、规模、长度）把每个请求送入 Mundane 或 Hard 池。", "ui.highest_throughput_and_lowest_first_toke":"基准数据中吞吐最高、首 token 延迟最低。为兼容既有配置而保留。", "ui.legacy":"旧版", "ui.registered_models":"已注册模型", "ui.show":"显示", "ui.deployable":"可部署", "ui.custom_providers":"自定义供应商", "ui.model":"模型", "ui.capabilities":"能力", "ui.context":"上下文", "ui.price_1m_in_out":"价格 /1M（输入 · 输出）", "ui.availability":"可用性", "ui.pools":"模型池", "ui.previous":"上一页", "ui.next":"下一页", "ui.fallback_and_escalation_always_keep_the_":"回退与升级始终保留请求所需的能力。决策在请求开始前完成，模型绝不会在流中途切换。", "ui.maximum_attempts_primary_fallbacks":"最大尝试次数（主选 + 回退）", "ui.what_counts_as_retryable":"哪些错误会重试", "ui.quality_floor_percentile_0_off":"质量下限（百分位，0 = 关闭）", "ui.needs_quality_scores_ignored_and_reporte":"需要质量分数；没有时会被忽略并在界面中说明。", "ui.what_the_quality_floor_does":"质量下限的作用", "ui.balanced_weighs_price_against_quality_th":"均衡会权衡价格与质量。下限会排除低于该百分位的模型，因此极便宜但很弱的模型无法胜出。设为 0 即可完全关闭。", "ui.messages":"消息数 ≥", "ui.prompt_characters":"提示字符数 ≥", "ui.how_request_signals_are_measured":"请求信号如何计量", "ui.mode":"模式", "ui.off":"关闭", "ui.manual_client_sends_x_geek_escalate":"手动（客户端发送 x-geek-escalate）", "ui.auto_after_repeated_upstream_failures":"自动（上游反复失败后）", "ui.failures_before_escalating":"升级前失败次数", "ui.max_escalations_per_conversation":"每次对话最多升级次数", "ui.destination_pool":"目标池", "ui.when_escalation_triggers":"何时触发升级", "ui.remember_for_minutes":"记忆时长（分钟）", "ui.what_continuity_does":"连续性的作用", "ui.save_routing_policy":"保存路由策略", "ui.dry_run_shows_which_model_auto_would_cho":"预演：显示 Auto 会选择哪个模型及其原因。不会向上游发送任何内容。", "ui.messages_2":"消息数", "ui.prompt_chars":"提示字符数", "ui.explain":"解释", "ui.three_filters_applied_in_order":"三道过滤器，按顺序应用。", "ui.how_each_strategy_maps_to_litellm_router":"各策略如何映射到 LiteLLM Router", "ui.strategy":"策略", "ui.import_json":"导入 JSON", "ui.new_profile":"新建配置", "ui.generates_configuration_that_points_a_cl":"生成指向此 GeekCubo 的客户端配置。密钥以环境变量引用，绝不写入文件。", "ui.search_tools":"搜索工具", "ui.routing_profile_or_model":"路由配置或模型", "ui.endpoint":"端点", "ui.format":"格式", "ui.download":"下载", "ui.add_source":"添加数据源", "ui.name":"名称", "ui.https_url_models_dev_compatible_json":"HTTPS 地址（兼容 models.dev 的 JSON）", "ui.save_source":"保存数据源", "ui.cancel":"取消", "ui.shows_what_each_enabled_source_reports_f":"显示每个已启用数据源对该模型的报告值，以及 GeekCubo 会采用哪一个。你自己配置的价格始终优先。", "ui.look_up":"查询", "ui.routing":"路由", "ui.volume":"总量", "ui.routing_decisions":"路由决策", "ui.how_auto_requests_were_classified_and_wh":"Auto 请求如何被分类以及去向。", "ui.by_tier":"按层级", "ui.by_strategy":"按策略", "ui.by_routing_id":"按路由 ID", "ui.top_models_served":"最常服务的模型", "ui.reliability":"可靠性", "ui.errors_by_cause":"按原因统计的错误", "ui.compare_against_a_baseline_model":"与基准模型对比", "ui.none":"无", "ui.compare":"对比", "ui.how_the_comparison_is_calculated":"对比如何计算", "ui.p50_and_p99_sourced_from_local_request_l":"p50 与 p99 —— 来自本地请求日志。", "ui.requests":"请求数", "ui.newest_first_click_a_row_to_copy_its_tra":"最新的在前。点击某行可复制其 trace ID。", "ui.when":"时间", "ui.tokens_in_out":"Token（输入 / 输出）", "ui.latency":"延迟", "ui.no_traffic_yet":"暂无流量", "ui.once_you_start_sending_requests_they_ll_":"一旦开始发送请求，它们会实时出现在这里。", "ui.expires":"过期", "ui.never":"永不过期", "ui.7_days":"7 天", "ui.30_days":"30 天", "ui.90_days":"90 天", "ui.1_year":"1 年", "ui.use_it_with_opencode":"与 OpenCode 一起使用：", "ui.created":"创建时间", "ui.last_used":"最近使用", "ui.actions":"操作", "ui.no_api_keys":"暂无 API 密钥", "ui.generate_one_above_to_start_sending_requ":"在上方生成一个，即可通过 SDK 或 CLI 发送请求。", "ui.administrator":"管理员", "ui.the_single_local_account_that_controls_t":"控制此安装的唯一本地账户。", "ui.password_was_reset_from_the_command_line":"密码已通过命令行重置", "ui.change_password":"修改密码", "ui.current_password":"当前密码", "ui.new_password":"新密码", "ui.confirm_new_password":"确认新密码", "ui.update_password":"更新密码", "ui.signed_in_browsers_for_this_administrato":"此管理员已登录的浏览器。会话在 12 小时或空闲 60 分钟后过期。", "ui.log_out_all_other_sessions":"退出所有其他会话", "ui.device":"设备", "ui.last_active":"最近活动", "ui.local_recovery":"本地恢复", "ui.password_recovery_is_local_only_by_desig":"密码恢复按设计仅限本地 —— 没有邮件重置，也没有可修改密码的公开接口。", "ui.open_a_shell_where_geekcubo_runs_host_or":"在 GeekCubo 运行的主机或容器中打开 shell。", "ui.choose_a_new_password_at_the_prompt_all_":"在提示处输入新密码。所有面板会话将被登出；API 密钥、供应商和使用数据不受影响。", "ui.artificial_analysis_api_key":"Artificial Analysis API 密钥", "ui.optional":"（可选）", "ui.save_key":"保存密钥", "ui.remove_stored_key":"移除已存储的密钥", "ui.how_quality_scoring_works":"质量评分如何工作", "ui.paste_it_above_and_save_it_is_encrypted_":"粘贴到上方并保存。它会静态加密存储，已缓存的内容会被丢弃，以便下次刷新使用新密钥。", "ui.quality_scores":"质量分数", "ui.where_these_numbers_come_from":"这些数字从何而来", "ui.manual":"手动", "ui.effective":"生效值", "ui.m_blended":"$/M 综合", "ui.help_and_docs":"帮助与文档", "ui.what_is_geekcubo":"GeekCubo 是什么？", "ui.60_second_quickstart":"60 秒快速上手", "ui.keyboard_shortcuts":"键盘快捷键", "ui.switch_tabs":"切换标签页", "ui.command_palette":"命令面板", "ui.toggle_this_help":"显示或隐藏此帮助", "ui.close_drawers_palette":"关闭抽屉 / 面板", "ui.going_further":"延伸阅读", "js.ov_empty_a":"暂无请求。", "js.ov_empty_b":"发送第一次调用后，它就会显示在这里。", "js.ra_unavailable":"路由分析不可用。", "js.no_spend":"此时间范围内尚无支出记录。", "js.no_traffic":"暂无流量", "toast.copied":"已复制到剪贴板", "toast.copy_blocked":"无法复制 — 浏览器已阻止", "toast.signed_in":"已以 {name} 登录", "toast.admin_created":"管理员 {name} 已创建", "toast.signed_out":"已退出登录", "toast.load_providers_failed":"无法加载供应商：{msg}", "toast.removed_provider":"已移除 {name}", "toast.api_key_empty":"API 密钥不能为空", "toast.saved_provider":"已保存 {name} 的密钥", "toast.load_custom_failed":"无法加载自定义供应商：{msg}", "toast.updated":"已更新 {name}", "toast.model_id_empty":"模型 ID 不能为空", "toast.model_id_dup":"该模型 ID 已注册", "toast.model_saved":"模型已保存", "toast.select_one_model":"请至少选择一个新模型", "toast.added_models_one":"已添加 1 个模型", "toast.added_models_many":"已添加 {count} 个模型", "toast.load_routing_failed":"无法加载路由：{msg}", "toast.routing_strategy":"路由策略：{name}", "toast.policy_saved":"路由策略已保存", "toast.load_models_failed":"无法加载模型：{msg}", "toast.load_analytics_failed":"无法加载分析数据：{msg}", "toast.load_keys_failed":"无法加载密钥：{msg}", "toast.revoked":"已撤销 {name}", "toast.name_empty":"名称不能为空", "toast.key_renamed":"密钥已重命名", "toast.name_first":"请先为密钥命名", "toast.created":"已创建 {name}", "toast.load_security_failed":"无法加载安全设置：{msg}", "toast.password_updated":"密码已更新 — 其他设备已退出登录", "toast.load_quality_failed":"无法加载质量分数：{msg}", "toast.score_range":"分数必须是 0 到 100 之间的数字", "toast.override_set":"已为 {name} 设置覆盖值", "toast.reset":"已重置 {name}", "toast.aa_saved":"Artificial Analysis 密钥已保存", "toast.stored_removed":"已移除存储的密钥", "toast.remove_key_failed":"无法移除密钥：{msg}", "toast.aa_refreshed":"已刷新 Artificial Analysis 分数", "toast.refresh_failed":"刷新失败：{msg}", "toast.load_profiles_failed":"无法加载路由配置：{msg}", "toast.duplicated":"已复制 {name}", "toast.now_default":"{name} 现在是默认配置", "toast.deleted":"已删除 {name}", "toast.default_reassigned":" — 默认配置现在是 auto", "toast.saved_profile":"已保存 {name}", "toast.file_too_large":"该文件过大，无法作为配置导出文件。", "toast.load_integrations_failed":"无法加载集成选项：{msg}", "toast.load_mi_failed":"无法加载模型数据源：{msg}", "toast.source_added":"数据源已添加", "toast.legacy_removed":"已移除旧版 \"__custom__\" 条目", "toast.saved_as":"已保存 {name} 为 {slug}。请在下方获取其模型。", "confirm.remove_provider":"移除 {name} 的密钥？路由到 {name} 的请求将开始失败。", "confirm.remove_model":"移除模型 {name}？", "confirm.remove_custom":"移除供应商 \"{name}\" 及其模型？", "confirm.sign_out_others":"退出此管理员在所有其他浏览器中的登录？", "confirm.reset_score":"将 {name} 重置为 AA 分数？", "confirm.remove_aa_key":"移除已存储的 Artificial Analysis 密钥？若设置了环境变量密钥，将重新使用它。", "confirm.change_slug":"将 API 标识符从 \"{old}\" 改为 \"{new}\"？\n\n所有发送 model: \"{old}\" 的客户端都将停止工作。", "confirm.delete_source":"删除此元数据源？", "confirm.legacy_remove":"永久移除旧版 \"__custom__\" 供应商密钥（{prefix}）？\n\n它不参与路由。若仍需要该密钥，请确认已另行保存 — 它无法恢复。", "confirm.revoke":"撤销 \"{name}\"？\n\n使用此密钥的客户端会立即收到 401。此操作不可撤销 — 如需再次访问，请签发新密钥。", "confirm.rotate":"轮换 \"{name}\"？\n\n将创建具有相同限制的替换密钥，且仅显示一次。\n\n确定 = 立即撤销旧密钥（即刻切换）。\n取消 = 保留旧密钥，直到你自己撤销它。", "prompt.rename_key":"将密钥 \"{name}\" 重命名为：", "prompt.set_score":"为 {name} 设置手动质量分数（0-100）：", "prompt.aa_current":"当前 AA 分数为：{score}", "prompt.override_note":"可选备注（为什么要覆盖？）：", "auth.session_expired":"会话已过期。请重新登录。", "auth.enter_creds":"请输入用户名和密码。", "auth.creds_required":"用户名和密码为必填项。", "auth.pw_mismatch":"两次密码不一致。", "auth.paste_token":"请粘贴服务器日志中的一次性安装令牌。", "auth.signed_out":"已退出登录。", "auth.pw_match":"两次密码一致。", "auth.pw_mismatch_yet":"两次密码尚不一致。", "auth.new_pw_mismatch":"两次新密码不一致。", "auth.fill_three":"请填写全部三个字段。", "qa.connection":"Artificial Analysis 连接", "qa.test":"测试连接", "qa.replace":"更换密钥", "qa.add":"添加密钥", "qa.remove":"移除密钥", "qa.last_sync":"最近一次成功同步", "qa.last_error":"最近错误", "qa.never":"尚未同步", "qa.from_env":"来自环境变量", "qa.saving":"正在保存…", "qa.key_hint":"在服务器上加密存储，保存后不再显示。旧密钥在此新密钥保存前一直有效。", "qa.daily_limit_label":"密钥的每日限额", "qa.daily_limit_hint":"每 24 小时的请求数，以 Artificial Analysis 账户页面为准。留空则使用文档中的 100/天。", "qa.status.not_configured":"未配置", "qa.status.connected":"已连接", "qa.status.invalid_key":"密钥无效", "qa.status.rate_limited":"已达限额", "qa.status.connection_failed":"连接失败", "qa.status.cached":"缓存数据", "pricing.legend":"定价", "pricing.allow_estimates":"允许在 Auto、最便宜策略和成本上限中使用参考估价", "pricing.allow_estimates_help":"默认关闭。仅比较已确认的供应商价格；只有参考估价的模型不会进入 Auto。开启后，每个基于估价的决策都会被标注。", "confirm.bulk_remove_models":"移除选中的 {count} 个模型{plural}？固定调用这些模型的请求将失败。", "nav.chat":"对话", "tab.chat.title":"对话", "tab.chat.sub":"与已部署的模型对话。与 SDK 流量一样经过路由、缓存与计费。", "ui.open_chat":"打开对话", "ui.open_chat_hint":"在浏览器中与已部署的模型对话——与 SDK 流量同样的路由、缓存与成本跟踪。", "chat.new":"新建对话", "chat.settings_title":"对话设置", "chat.default_title":"新对话", "chat.clear_history":"清空历史…", "chat.conversations_aria":"对话列表", "chat.model_aria":"模型", "chat.regenerate":"重新生成回复", "chat.empty_title":"问点什么吧。", "chat.empty_sub":"请求经由引擎路由——与 SDK 流量同样的路由、缓存与成本跟踪。", "chat.input_placeholder":"给 GeekCubo 发消息…", "chat.send":"发送", "chat.stop":"停止", "chat.system_prompt":"系统提示词…", "chat.system_prompt_set":"系统提示词 ✓", "chat.system_ph":"你是一个乐于助人的助手…", "chat.system_help":"留空 = 使用对话默认设置。按对话保存。", "chat.save_prompt":"保存提示词", "chat.default_model":"默认模型", "chat.default_model_help":"用于新对话。对话内的模型选择器可覆盖它。", "chat.temperature":"温度", "chat.max_tokens":"最大输出 token", "chat.default_system_prompt":"默认系统提示词", "chat.default_system_prompt_ph":"你是一个简洁的工程助手。", "chat.default_system_help":"适用于没有专属提示词的对话。", "chat.save_history":"在此服务器上保存聊天历史", "chat.retention_days":"对话保留天数", "chat.retention_help":"超期的对话会被清理。留空则永久保留。", "chat.font_size":"消息字号", "chat.fs_small":"小", "chat.fs_medium":"中", "chat.fs_large":"大", "chat.enter_to_send":"按 Enter 直接发送", "chat.privacy_note":"对话保存在本服务器数据库中。请求会发送到你配置的供应商，与 SDK 流量完全一致。", "chat.privacy_ack":"我已了解聊天数据会发送到已配置的供应商", "chat.save_settings":"保存设置", "chat.model_auto":"自动（由路由器选择）", "chat.no_conversations":"还没有对话。", "chat.delete_convo_title":"删除此对话", "chat.kbd_enter_send":"Enter 发送 · Shift+Enter 换行", "chat.kbd_ctrl_enter_send":"Ctrl+Enter 发送 · Enter 换行", "chat.tokens_meta":"输入 {in} · 输出 {out}", "chat.error_note":"生成在完成前被中断。", "chat.upstream_error":"上游模型返回了错误。", "toast.chat_load_failed":"无法加载聊天数据：{msg}", "toast.chat_failed":"聊天请求失败：{msg}", "toast.chat_convo_deleted":"对话已删除", "toast.chat_cleared":"已清理 {count} 个对话", "toast.chat_temp_range":"温度必须在 0 到 2 之间", "toast.chat_settings_saved":"聊天设置已保存", "toast.chat_open_convo":"请先打开一个对话", "toast.chat_saved_prompt":"已保存此对话的系统提示词", "confirm.delete_conversation":"删除此对话？\n\n消息将从服务器数据库中移除。用量与费用记录仍保留在分析中。", "confirm.clear_chat_history":"删除全部已保存的对话？\n\n本服务器上存储的所有聊天消息都会被移除。用量与费用记录仍保留在分析中。", "q.ov_score":"手动评分（0–100）", "q.ov_note":"备注", "q.ov_model_ph":"例如 openai/gpt-4o, anthropic/claude-…", "q.ov_note_ph":"为什么覆盖 AA 评分", "q.ov_apply":"应用覆盖", "q.ov_clear":"清除覆盖", "q.ov_help":"一个或多个模型 ID，以逗号分隔 — 覆盖会应用到列出的每个模型。手动评分始终优先于 AA 评分。", "toast.q_ids_required":"请输入至少一个模型 ID", "toast.q_too_many":"批量操作最多 500 个模型 ID", "toast.q_bulk_set":"已为 {count} 个模型设置覆盖", "toast.q_bulk_clear":"已清除 {count} 个模型的覆盖", "providers.bulk_actions":"批量模型操作", "providers.select_all":"全选", "providers.selected_count":"已选 {count} 个", "providers.bulk_capability":"能力", "providers.bulk_capability_state":"能力状态", "providers.cap_tools":"工具", "providers.cap_vision":"视觉", "providers.cap_supported":"支持", "providers.cap_unsupported":"不支持", "providers.cap_unknown":"未知", "providers.cap_catalog":"使用目录", "providers.cap_json_mode":"JSON 模式", "providers.cap_json_schema":"JSON Schema", "providers.apply":"应用", "providers.enable":"启用", "providers.disable":"停用", "providers.remove_selected":"移除所选", "providers.resolve_metadata":"解析", "toast.metadata_resolved":"元数据：{resolved} 已解析，{ambiguous} 有歧义，{unmatched} 未匹配，{failed} 失败。", "select.search_ph":"搜索目录键…", "providers.catalog_key_ph":"搜索目录键…", "select.remove_item":"移除 {name}", "select.use_custom":"使用“{name}”", "select.no_matches":"没有匹配的模型", "select.more_results":"还有 {count} 个——继续输入以缩小范围", "q.ov_model_search_ph":"搜索并选择模型…", "q.ov_help_picker":"搜索并选择一个或多个模型，或在下表中勾选行。手动评分始终优先于 AA 评分。", "q.filter_ph":"筛选模型…", "q.select_filtered":"选择筛选结果", "q.select_all_filtered":"选择所有筛选出的模型", "q.deselect_all":"取消全选", "q.bulk_set":"为所选设置评分", "q.bulk_clear":"清除所选覆盖", "q.select_model":"选择 {name}", "confirm.q_bulk_clear":"清除 {count} 个所选模型的手动覆盖？", "qa.daily_limit_short":"每日限额", "chat.attach":"附加文件", "chat.attach_drop":"拖放文件以附加", "chat.attach_remove":"移除附件", "chat.attach_unreadable":"无法读取此文件；只会发送文件名。", "chat.attach_uploading":"上传中…", "chat.attach_too_large":"文件过大（最大 {max} MB）", "toast.chat_attach_failed":"无法附加 {name}：{msg}", "toast.chat_attach_disabled":"此服务器已禁用附件。", "toast.chat_attach_too_many":"每条消息最多 {max} 个附件。", "toast.chat_attach_extract_failed":"{name}：无法读取（{msg}）", "toast.chat_attach_wait":"请等待上传完成。", "chat.search_toggle":"网络搜索", "chat.search_settings":"网络搜索", "chat.search_help":"启用后，GeekCubo 会在回答前搜索网络并引用所用页面。结果会作为系统消息注入，因此任何模型都能使用。", "chat.search_mode":"搜索模式", "chat.search_mode_off":"关闭", "chat.search_mode_manual":"手动（每条消息）", "chat.search_mode_auto":"自动（预留）", "chat.search_mode_help":"手动模式会在输入框旁显示开关。自动模式为预留功能，尚未实现。", "chat.search_backend":"搜索后端", "chat.search_backend_none":"选择后端…", "chat.search_backend_searxng":"SearXNG（自托管）", "chat.search_backend_brave":"Brave 搜索 API", "chat.search_backend_tavily":"Tavily", "chat.search_url":"SearXNG 地址", "chat.search_url_ph":"http://searxng:8080/", "chat.search_url_help":"你的 SearXNG 实例的基础 URL。安装脚本的 search 配置会在内部网络提供该服务。", "chat.search_api_key":"API 密钥", "chat.search_api_key_ph":"粘贴新密钥以替换已保存的密钥", "chat.search_key_clear":"移除已保存的密钥", "chat.search_key_help":"在此服务器上加密存储，之后不再显示。Brave 和 Tavily 需要密钥；SearXNG 不需要。", "chat.search_max_searches":"每个对话最多搜索次数", "chat.search_max_results":"每次搜索的结果数", "chat.search_max_fetches":"每次搜索抓取的页面数", "chat.search_timeout":"搜索超时（秒）", "chat.search_test":"测试连接", "chat.search_testing":"测试中…", "chat.search_test_ok":"{ms} 毫秒内返回 {count} 条结果", "chat.search_test_failed":"搜索测试失败：{msg}", "chat.search_key_state_unset":"未保存密钥", "chat.search_key_state_set":"已保存密钥", "chat.search_key_state_undecryptable":"已保存的密钥无法解密", "chat.context_budget":"上下文：{tokens} / {budget} tokens", "chat.context_omitted":"已省略 {count} 条较早的消息", "chat.sources":"来源", "chat.search_used":"网络搜索：{backend}", "toast.search_saved":"网络搜索设置已保存", "toast.search_save_failed":"无法保存网络搜索设置：{msg}", "toast.search_test_failed":"网络搜索测试失败", "nav.local":"本地 AI", "tab.local.title":"本地 AI", "tab.local.sub":"通过此路由器使用你自己机器上的模型。", "local.title":"本地 AI 连接", "local.sub":"路由到运行在你自己机器上的模型。一个小型连接器主动拨号到本服务器，因此无需开放端口，也不需要入站隧道。", "local.refresh":"刷新", "local.setup_button":"设置机器", "local.feature_off_title":"服务器上已关闭本地 AI 连接", "local.feature_off_body":"在服务器环境中设置 LOCAL_CONNECT_ENABLED=true 并重启，然后重新加载此页面。", "local.url_missing_title":"未配置公开地址", "local.url_missing_body":"将 LOCAL_CONNECT_PUBLIC_URL 设置为连接器应拨号的地址（例如 https://example.com），以便自动填充安装命令和服务文件。", "local.settings_title":"路由行为", "local.settings_sub":"控制本地模型是否参与自动路由，以及请求是否可以回退到云端。", "local.set_enabled":"允许本地机器参与路由", "local.set_auto":"将本地模型纳入自动选择", "local.set_no_fallback":"本地模型失败时绝不回退到云端", "local.settings_help":"只有当本地模型的价格确认为零，且机器已批准并在线时，才会被纳入自动选择。开启“绝不回退”后，仅本地请求会失败，而不会由云端提供商处理。", "local.save_settings":"保存", "local.settings_saved":"本地路由设置已保存。", "local.machines_title":"机器", "local.machines_sub":"每台机器对应一个连接器。待批准的机器可见，但在批准之前不会接收流量。", "local.machines_empty":"尚无机器。使用“设置机器”生成注册码。", "local.enrollments_title":"注册码", "local.enrollments_sub":"一次性注册码，用于让连接器注册。每台机器首次连接时即消耗一个注册码。", "local.new_code":"新建注册码", "local.install_title":"安装连接器", "local.install_sub":"在托管模型的机器上运行（Ollama、LM Studio、vLLM、llama.cpp 或任何 [OI] 兼容服务器）。", "local.service_files":"作为服务运行", "local.delete":"删除", "local.never":"从未", "local.ctx_suffix":"上下文", "local.ctx_unknown":"上下文未知", "local.no_models":"此机器尚未上报任何模型。", "local.no_enrollments":"没有注册码。", "local.enroll_active":"有效", "local.enroll_used":"已使用", "local.status_online":"在线", "local.status_offline":"离线", "local.status_pending":"待批准", "local.status_approved":"已批准", "local.status_revoked":"已撤销", "local.pending_note":"此机器正在等待批准。模型已列出，但不会接收流量。", "local.action_approve":"批准", "local.action_discover":"发现模型", "local.action_revoke":"撤销", "local.action_rotate":"轮换凭据", "local.action_delete":"删除", "local.meta_host":"主机名", "local.meta_platform":"平台", "local.meta_agent":"连接器版本", "local.meta_adapters":"适配器", "local.meta_seen":"最后出现", "local.col_model":"模型", "local.col_adapter":"适配器类型", "local.col_context":"上下文", "local.col_caps":"能力", "local.col_enabled":"已启用", "local.kpi_machines":"机器", "local.kpi_online":"当前在线", "local.kpi_pending":"待批准", "local.kpi_models":"模型", "local.toast_approved":"机器已批准。", "local.toast_revoked":"机器已撤销。", "local.toast_deleted":"机器已删除。", "local.toast_discovered":"模型列表已刷新。", "local.confirm_revoke":"撤销此机器？其连接器将立即断开，并且在轮换凭据之前无法重新连接。", "local.confirm_delete_machine":"删除此机器及其模型列表？此操作无法撤销。", "local.confirm_rotate":"轮换此机器的凭据？正在运行的连接器会继续工作直到重新连接，之后旧凭据将被拒绝。", "local.confirm_delete_enrollment":"删除此注册码？", "local.credential_once_title":"立即复制新凭据", "local.credential_once_body":"它只显示一次。请将其保存到该机器上的连接器配置中。", "local.wizard_title":"连接本地机器", "local.wizard_close":"关闭", "local.wizard_back":"上一步", "local.wizard_next":"下一步", "local.wizard_done":"完成", "local.step1":"启用", "local.step2":"注册码", "local.step3":"安装", "local.step4":"注册", "local.step5":"启动", "local.step6":"批准", "local.step7":"模型", "local.step8":"自动路由", "local.w0_title":"开启功能", "local.w0_body":"本地 AI 连接是一项服务器端功能。必须先启用它，连接器才能注册。", "local.w0_ready":"功能已启用。继续创建注册码。", "local.w0_blocked":"此服务器上该功能已禁用。设置 LOCAL_CONNECT_ENABLED=true 并重启，然后重新加载此页面。", "local.w1_title":"创建注册码", "local.w1_body":"一次性注册码授权单个连接器进行注册。它会在短时间后过期。", "local.w1_name":"机器名称（可选）", "local.w1_name_ph":"例如 office-gpu", "local.w1_name_help":"用于在列表中识别此机器的标签。你可以稍后重命名。", "local.w1_created":"注册码已创建", "local.w2_title":"安装连接器包", "local.w2_body":"在托管模型的机器上安装连接器。需要 Python 3.11 或更高版本。", "local.w2_note":"请安装到虚拟环境中，以与系统软件包隔离。", "local.w3_title":"注册机器", "local.w3_body":"使用第 2 步的注册码运行注册命令。凭据会写入连接器配置文件。", "local.w3_note":"注册码只能使用一次。如果已过期，请创建新的。", "local.w4_title":"启动连接器", "local.w4_body":"在前台运行连接器以观察其连接，然后将其转为服务。", "local.w4_note":"连接器保持一个出站 WebSocket 连接，并会自动重连。", "local.w5_title":"等待机器出现", "local.w5_body":"连接器连接后，机器会显示在这里。若稍慢，请刷新。", "local.w5_seen":"{name} 已连接。", "local.w5_waiting":"尚无机器连接。", "local.w5_recheck":"再次检查", "local.w6_title":"批准机器", "local.w6_body":"新机器会保持待批准状态，直到管理员批准。在此之前不会有任何流量路由到它。", "local.w6_none":"暂无可批准的机器。", "local.w6_must_approve":"请先批准待处理的机器再继续。", "local.w7_title":"在自动路由中启用本地模型", "local.w7_body":"开启“将本地模型纳入自动选择”，并启用你希望路由到的模型。只有当价格确认为零时，本地模型才会被自动选择。", "local.w7_done":"设置完成。本地模型现在会出现在提供商和路由页面中。" },
  hi: { "q.tabs_label":"गुणवत्ता अनुभाग", "q.tab_models":"मॉडल", "q.tab_scores":"गुणवत्ता स्कोर", "q.tab_aa":"Artificial Analysis कनेक्शन", "q.col_availability":"उपलब्धता", "q.avail_yes":"उपलब्ध", "q.avail_no":"प्रदाता कुंजी नहीं", "q.avail_no_title":"कोई कॉन्फ़िगर की गई प्रदाता कुंजी इस मॉडल को सेवा नहीं देती। केवल बेंचमार्क डेटा से मॉडल तैनात करने योग्य नहीं बनता।", "q.sync_title":"बेंचमार्क सिंक्रनाइज़ेशन", "q.sync_last_ok":"अंतिम सफल सिंक", "q.sync_last_attempt":"नवीनतम प्रयास", "q.sync_returned":"AA द्वारा लौटाए गए मॉडल", "q.sync_matched":"कैटलॉग से मिलान", "q.sync_unmatched":"बिना मिलान", "q.sync_overrides":"मैन्युअल ओवरराइड", "q.sync_outcome_ok":"सफल", "q.sync_outcome_failed":"विफल", "q.sync_need_key":"बेंचमार्क स्कोर सिंक करने के लिए Artificial Analysis टैब पर कुंजी जोड़ें। मैन्युअल ओवरराइड बिना कुंजी के काम करते हैं।", "q.sync_never":"इस कुंजी से अभी तक कोई सिंक नहीं हुआ है। AA से रीफ़्रेश करें का उपयोग करें।", "q.sync_no_models":"पिछले सिंक में कोई मॉडल नहीं लौटा।", "q.status_line":"बेंचमार्क डेटा वाले {matched} मॉडल · {overrides} मैन्युअल ओवरराइड", "q.src.live":"लाइव", "q.src.stale_cache":"कैश (AA पहुँच से बाहर)", "q.src.stale_db":"कैश (सहेजा गया स्नैपशॉट)", "q.src.error":"सिंक विफल", "q.src.missing_key":"API कुंजी नहीं", "q.auto_status":"ऑटो-रूटिंग स्थिति", "q.auto_status_hint":"model=\"auto\" अभी कौन-सा मॉडल चुनेगा। यह कॉन्फ़िगर किए गए प्रदाताओं पर निर्भर करता है, बेंचमार्क सिंक पर नहीं।", "q.auto_no_provider":"कोई तैनात करने योग्य मॉडल वर्तमान आवश्यकताओं को पूरा नहीं करता। प्रदाता पृष्ठ पर प्रदाता कुंजी जोड़ें। यह Artificial Analysis सिंक से अलग है।", "qa.credential":"API कुंजी", "qa.cred_stored":"इस सर्वर पर संग्रहीत (एन्क्रिप्टेड)", "qa.cred_env":"सर्वर परिवेश से", "qa.last_test":"अंतिम कनेक्शन परीक्षण", "qa.last_test_ok":"अंतिम सफल परीक्षण", "qa.not_tested":"अभी परीक्षण नहीं हुआ", "qa.sync_status":"बेंचमार्क सिंक", "qa.tier":"{tier} योजना", "qa.troubleshooting":"कनेक्शन समस्या निवारण", "qa.status.key_configured":"कुंजी कॉन्फ़िगर की गई", "qa.sync.not_configured":"कॉन्फ़िगर नहीं", "qa.sync.never_synced":"कभी सिंक नहीं हुआ", "qa.sync.synced":"सिंक हो गया", "qa.sync.sync_failed":"सिंक विफल", "qa.err.invalid_key":"अमान्य कुंजी", "qa.err.insufficient_tier":"योजना में यह एंडपॉइंट शामिल नहीं", "qa.err.endpoint_retired":"एंडपॉइंट बंद", "qa.err.rate_limited":"दर सीमा पूरी", "qa.err.timeout":"समय समाप्त", "qa.err.malformed_response":"अप्रत्याशित प्रतिक्रिया", "qa.err.no_data":"कोई मॉडल नहीं लौटा", "qa.err.no_catalog_match":"कोई कैटलॉग मिलान नहीं", "qa.err.server_error":"AA सर्वर त्रुटि", "qa.err.connection_failed":"कनेक्शन विफल", "auth.tagline":"एक गेटवे। हर AI मॉडल।", "auth.welcome":"वापसी पर स्वागत है", "auth.subtitle":"इस GeekCubo इंस्टॉलेशन के प्रशासक कंसोल में साइन इन करें।", "auth.api_key":"API कुंजी", "auth.continue":"जारी रखें", "nav.search":"खोज", "nav.overview":"अवलोकन", "nav.providers":"प्रदाता", "nav.routing":"रूटिंग", "nav.analytics":"एनालिटिक्स", "nav.api_keys":"API कुंजियाँ", "nav.help_docs":"सहायता और दस्तावेज़", "nav.sign_out":"साइन आउट", "status.connected":"कनेक्टेड", "status.disconnected":"डिस्कनेक्टेड", "auth.checking":"जाँच हो रही है…", "auth.welcome_aboard":"स्वागत है।", "auth.key_invalid":"यह कुंजी काम नहीं कर रही। sk-geek- प्रीफिक्स जाँचें…", "tab.overview.title":"ओवरव्यू", "tab.overview.sub":"आपका सिंगल-टेनेंट LLM राउटर एक नज़र में।", "tab.providers.title":"प्रोवाइडर कुंजियाँ", "tab.providers.sub":"BYOK — स्टोरेज में एन्क्रिप्टेड, अपस्ट्रीम LLM कॉल के लिए उपयोग।", "tab.routing.title":"रूटिंग", "tab.routing.sub":"model='auto' हर अनुरोध के लिए सही मॉडल कैसे चुनता है।", "tab.analytics.title":"एनालिटिक्स", "tab.analytics.sub":"केवल स्थानीय खर्च, लेटेंसी और अनुरोध इतिहास।", "tab.keys.title":"API कुंजियाँ", "tab.keys.sub":"SDK और CLI अनुमान अनुरोध प्रमाणित करने वाली sk-geek-* कुंजियाँ।", "nav.quality":"गुणवत्ता", "tab.quality.title":"गुणवत्ता स्कोर", "tab.quality.sub":"quality रूटिंग रणनीति के लिए वास्तविक बेंचमार्क स्कोर। Artificial Analysis से लिए गए।", "auth.username":"उपयोगकर्ता नाम", "auth.password":"पासवर्ड", "auth.sign_in":"साइन इन", "nav.security":"सुरक्षा", "tab.security.title":"सुरक्षा", "tab.security.sub":"प्रशासक खाता, पासवर्ड और सत्र।", "tab.profiles.title":"रूटिंग प्रोफ़ाइल", "tab.profiles.sub":"नामित Auto कॉन्फ़िगरेशन जिन्हें क्लाइंट मॉडल आईडी से चुनते हैं।", "tab.integrations.title":"टूल जोड़ें", "tab.integrations.sub":"OpenCode, Claude Code, Cursor और अन्य के लिए तैयार कॉन्फ़िगरेशन।", "tab.intelligence.title":"मॉडल डेटा", "tab.intelligence.sub":"मॉडल की कीमतें और सीमाएँ कहाँ से आती हैं।", "auth.loading":"लोड हो रहा है…", "auth.checking_status":"प्रशासक स्थिति जाँची जा रही है।", "auth.signin_title":"साइन इन करें", "auth.signin_sub":"इस GeekCubo इंस्टॉलेशन तक प्रशासक पहुँच।", "auth.forgot":"पासवर्ड भूल गए?", "auth.reset_hint":"इसे होस्ट या कंटेनर पर रीसेट करें:", "auth.reset_note":"कुंजियाँ, प्रदाता और उपयोग अप्रभावित रहते हैं।", "auth.setup_title":"प्रशासक खाता बनाएँ", "auth.setup_sub":"इस GeekCubo इंस्टॉलेशन को नियंत्रित करता है: प्रदाता क्रेडेंशियल, API कुंजियाँ और रूटिंग।", "auth.min_password":"कम से कम 8 अक्षर", "auth.confirm_password":"पासवर्ड की पुष्टि करें", "auth.setup_token":"सेटअप टोकन", "auth.from_log":"सर्वर लॉग से", "auth.create_admin":"प्रशासक बनाएँ", "auth.where_token":"सेटअप टोकन कहाँ है?", "auth.token_hint":"पहली बार शुरू होने पर सर्वर लॉग में छपता है। नया जारी करने के लिए:", "auth.toggle_password":"पासवर्ड दिखाएँ या छिपाएँ", "ov.spend":"खर्च (7 दिन)", "ov.savings":"रूटिंग बचत", "ov.p50":"p50 विलंबता", "ov.models":"उपयोग योग्य मॉडल", "ov.quickstart":"त्वरित शुरुआत", "ov.recent":"हाल की गतिविधि", "prov.title":"प्रदाता कुंजियाँ", "prov.tab_std":"मानक प्रदाता", "prov.tab_custom":"कस्टम प्रदाता", "routing.strategy":"रूटिंग रणनीति", "routing.pools":"मॉडल पूल", "routing.advanced":"फ़ॉलबैक, एस्केलेशन और निरंतरता", "routing.explain":"रूटिंग निर्णय जाँचें", "profiles.title":"रूटिंग प्रोफ़ाइल", "int.title":"अपना AI टूल जोड़ें", "md.title":"मॉडल डेटा स्रोत", "md.lookup":"मूल्य खोज", "an.spend":"मॉडल के अनुसार खर्च", "an.latency":"प्रदाता के अनुसार विलंबता", "an.recent":"हाल के अनुरोध", "keys.title":"राउटर API कुंजियाँ", "sec.sessions":"सत्र", "q.setup":"गुणवत्ता स्कोरिंग सेट करें", "q.models":"मॉडल", "preset.heading":"प्रीसेट से शुरू करें", "preset.sub":"टेम्पलेट एडिटर में पहले से भर जाते हैं — सहेजने से पहले कुछ भी बदलें।", "preset.economy":"हर अनुरोध के लिए सबसे सस्ता सक्षम मॉडल। न्यूनतम खर्च, कोई गुणवत्ता सीमा नहीं।", "preset.premium":"सबसे मज़बूत मॉडल पहले, कीमत की परवाह नहीं। गुणवत्ता-प्रधान काम के लिए।", "preset.coding":"टूल कॉल और लंबे प्रॉम्प्ट Hard पूल में जाते हैं। एजेंट और एडिटर काम के लिए।", "preset.fast":"संतुलित रूटिंग जो पूल में कम विलंबता पसंद करती है।", "ui.profiles":"प्रोफ़ाइल", "ui.security":"सुरक्षा", "ui.api_keys":"API कुंजियाँ", "ui.connect_a_tool":"टूल जोड़ें", "ui.model_data":"मॉडल डेटा", "ui.connecting":"कनेक्ट हो रहा है…", "ui.language":"भाषा", "ui.light":"हल्का", "ui.system":"सिस्टम", "ui.dark":"गहरा", "ui.openai_compatible_base_url":"OpenAI-संगत बेस URL", "ui.copy":"कॉपी करें", "ui.use_this_in_any_openai_compatible_client":"किसी भी OpenAI-संगत क्लाइंट में उपयोग करें।", "ui.signed_in":"साइन इन है", "ui.security_and_sessions":"सुरक्षा और सत्र", "ui.api_keys_2":"API कुंजियाँ", "ui.sign_out":"साइन आउट", "ui.you_re_up_point_any_openai_sdk_at_your_b":"सब तैयार — किसी भी OpenAI SDK को अपने बेस URL पर इंगित करें।", "ui.last_5_requests_routed_through_this_serv":"इस सर्वर से गए अंतिम 5 अनुरोध।", "ui.view_all":"सभी देखें", "ui.no_requests_yet":"अभी कोई अनुरोध नहीं।", "ui.new_here_get_fully_set_up_in_2_minutes":"पहली बार? 2 मिनट में पूरा सेटअप", "ui.re_enter_as_a_named_provider":"नामित प्रदाता के रूप में दोबारा दर्ज करें", "ui.remove_legacy_entry":"लीगेसी प्रविष्टि हटाएँ", "ui.provider":"प्रदाता", "ui.others_openai_format":"अन्य (OpenAI प्रारूप)", "ui.api_key":"API कुंजी", "ui.provider_name":"प्रदाता नाम", "ui.display_name_a_unique_internal_slug_is_d":"प्रदर्शित नाम। एक अद्वितीय आंतरिक स्लग स्वतः बनता है।", "ui.api_base_url":"API बेस URL", "ui.usually_ends_in_v1_must_be_https_unless_":"सामान्यतः /v1 पर समाप्त होता है। https होना चाहिए जब तक होस्ट CUSTOM_PROVIDER_ALLOWED_LOCAL_HOSTS में न हो।", "ui.api_key_2":"API कुंजी", "ui.encrypted_at_rest_never_displayed_again_":"संग्रहण में एन्क्रिप्टेड। सहेजने के बाद कभी नहीं दिखाई जाती।", "ui.prefix":"उपसर्ग", "ui.status":"स्थिति", "ui.no_provider_keys_yet":"अभी कोई प्रदाता कुंजी नहीं", "ui.add_at_least_one_to_start_routing_real_t":"वास्तविक ट्रैफ़िक रूट करने के लिए कम से कम एक जोड़ें। ऊपर से प्रदाता चुनें या त्वरित-जोड़ पर क्लिक करें।", "ui.lowest_cost_that_clears_your_quality_flo":"वह सबसे कम लागत जो आपकी गुणवत्ता सीमा पार करे। किसी भी संख्या में प्रदाताओं के साथ सुरक्षित डिफ़ॉल्ट।", "ui.recommended":"अनुशंसित", "ui.lowest_per_token_cost_meeting_the_reques":"अनुरोध की क्षमताओं को पूरा करते हुए सबसे कम प्रति-टोकन लागत। आउटपुट गुणवत्ता भिन्न हो सकती है।", "ui.highest_score_from_artificial_analysis_o":"Artificial Analysis से उच्चतम स्कोर या आपके मैनुअल ओवरराइड। स्कोर न होने पर कीमत को अनुमान के रूप में उपयोग करता है।", "ui.re_ranks_by_observed_success_rate_and_la":"जब प्रत्येक मॉडल के यहाँ 20+ अनुरोध हो जाते हैं, तो देखी गई सफलता दर और विलंबता से पुनः क्रमबद्ध करता है। तब तक: संतुलित।", "ui.sends_each_request_to_your_mundane_or_ha":"प्रत्येक अनुरोध को देखने योग्य संकेतों (टूल, आकार, लंबाई) के आधार पर आपके Mundane या Hard पूल में भेजता है।", "ui.highest_throughput_and_lowest_first_toke":"बेंचमार्क डेटा से उच्चतम थ्रूपुट और न्यूनतम प्रथम-टोकन विलंबता। मौजूदा कॉन्फ़िगरेशन की संगतता के लिए रखा गया।", "ui.legacy":"लीगेसी", "ui.registered_models":"पंजीकृत मॉडल", "ui.show":"दिखाएँ", "ui.deployable":"तैनात करने योग्य", "ui.custom_providers":"कस्टम प्रदाता", "ui.model":"मॉडल", "ui.capabilities":"क्षमताएँ", "ui.context":"संदर्भ", "ui.price_1m_in_out":"मूल्य /1M (इन · आउट)", "ui.availability":"उपलब्धता", "ui.pools":"पूल", "ui.previous":"पिछला", "ui.next":"अगला", "ui.fallback_and_escalation_always_keep_the_":"फ़ॉलबैक और एस्केलेशन हमेशा अनुरोध की आवश्यक क्षमताएँ बनाए रखते हैं। निर्णय अनुरोध शुरू होने से पहले लिए जाते हैं; स्ट्रीम के बीच में मॉडल कभी नहीं बदलता।", "ui.maximum_attempts_primary_fallbacks":"अधिकतम प्रयास (प्राथमिक + फ़ॉलबैक)", "ui.what_counts_as_retryable":"कौन-सी त्रुटियाँ पुनः प्रयास योग्य हैं", "ui.quality_floor_percentile_0_off":"गुणवत्ता सीमा (प्रतिशतक, 0 = बंद)", "ui.needs_quality_scores_ignored_and_reporte":"गुणवत्ता स्कोर चाहिए; न होने पर अनदेखा किया जाता है (और बताया जाता है)।", "ui.what_the_quality_floor_does":"गुणवत्ता सीमा क्या करती है", "ui.balanced_weighs_price_against_quality_th":"संतुलित कीमत और गुणवत्ता को तौलता है। सीमा उस प्रतिशतक से नीचे के मॉडल हटा देती है, इसलिए बहुत सस्ता पर कमज़ोर मॉडल जीत नहीं सकता। पूरी तरह बंद करने के लिए 0 रखें।", "ui.messages":"संदेश ≥", "ui.prompt_characters":"प्रॉम्प्ट अक्षर ≥", "ui.how_request_signals_are_measured":"अनुरोध संकेत कैसे मापे जाते हैं", "ui.mode":"मोड", "ui.off":"बंद", "ui.manual_client_sends_x_geek_escalate":"मैनुअल (क्लाइंट x-geek-escalate भेजता है)", "ui.auto_after_repeated_upstream_failures":"स्वतः (अपस्ट्रीम विफलताओं के दोहराव के बाद)", "ui.failures_before_escalating":"एस्केलेशन से पहले विफलताएँ", "ui.max_escalations_per_conversation":"प्रति बातचीत अधिकतम एस्केलेशन", "ui.destination_pool":"गंतव्य पूल", "ui.when_escalation_triggers":"एस्केलेशन कब सक्रिय होता है", "ui.remember_for_minutes":"याद रखें (मिनट)", "ui.what_continuity_does":"निरंतरता क्या करती है", "ui.save_routing_policy":"रूटिंग नीति सहेजें", "ui.dry_run_shows_which_model_auto_would_cho":"ड्राई-रन: दिखाता है कि Auto कौन-सा मॉडल चुनेगा और क्यों। अपस्ट्रीम कुछ नहीं भेजा जाता।", "ui.messages_2":"संदेश", "ui.prompt_chars":"प्रॉम्प्ट अक्षर", "ui.explain":"समझाएँ", "ui.three_filters_applied_in_order":"तीन फ़िल्टर, क्रम से लागू।", "ui.how_each_strategy_maps_to_litellm_router":"प्रत्येक रणनीति LiteLLM Router में कैसे मैप होती है", "ui.strategy":"रणनीति", "ui.import_json":"JSON आयात करें", "ui.new_profile":"नई प्रोफ़ाइल", "ui.generates_configuration_that_points_a_cl":"ऐसा कॉन्फ़िगरेशन बनाता है जो क्लाइंट को इस GeekCubo पर इंगित करे। कुंजियाँ पर्यावरण चर से संदर्भित होती हैं, कभी एम्बेड नहीं।", "ui.search_tools":"टूल खोजें", "ui.routing_profile_or_model":"रूटिंग प्रोफ़ाइल या मॉडल", "ui.endpoint":"एंडपॉइंट", "ui.format":"प्रारूप", "ui.download":"डाउनलोड", "ui.add_source":"स्रोत जोड़ें", "ui.name":"नाम", "ui.https_url_models_dev_compatible_json":"HTTPS URL (models.dev-संगत JSON)", "ui.save_source":"स्रोत सहेजें", "ui.cancel":"रद्द करें", "ui.shows_what_each_enabled_source_reports_f":"दिखाता है कि प्रत्येक सक्षम स्रोत उस मॉडल के लिए क्या बताता है और GeekCubo कौन-सा मान लेगा। आपकी स्वयं की सेट की गई कीमतें हमेशा जीतती हैं।", "ui.look_up":"खोजें", "ui.routing":"रूटिंग", "ui.volume":"मात्रा", "ui.routing_decisions":"रूटिंग निर्णय", "ui.how_auto_requests_were_classified_and_wh":"Auto अनुरोध कैसे वर्गीकृत हुए और कहाँ गए।", "ui.by_tier":"स्तर के अनुसार", "ui.by_strategy":"रणनीति के अनुसार", "ui.by_routing_id":"रूटिंग आईडी के अनुसार", "ui.top_models_served":"सर्वाधिक सेवित मॉडल", "ui.reliability":"विश्वसनीयता", "ui.errors_by_cause":"कारण के अनुसार त्रुटियाँ", "ui.compare_against_a_baseline_model":"आधार मॉडल से तुलना करें", "ui.none":"कोई नहीं", "ui.compare":"तुलना करें", "ui.how_the_comparison_is_calculated":"तुलना कैसे गणना की जाती है", "ui.p50_and_p99_sourced_from_local_request_l":"p50 और p99 — स्थानीय अनुरोध लॉग से।", "ui.requests":"अनुरोध", "ui.newest_first_click_a_row_to_copy_its_tra":"नवीनतम पहले। trace ID कॉपी करने के लिए पंक्ति पर क्लिक करें।", "ui.when":"कब", "ui.tokens_in_out":"टोकन (इन / आउट)", "ui.latency":"विलंबता", "ui.no_traffic_yet":"अभी कोई ट्रैफ़िक नहीं", "ui.once_you_start_sending_requests_they_ll_":"अनुरोध भेजना शुरू करते ही वे यहाँ वास्तविक समय में दिखेंगे।", "ui.expires":"समाप्ति", "ui.never":"कभी नहीं", "ui.7_days":"7 दिन", "ui.30_days":"30 दिन", "ui.90_days":"90 दिन", "ui.1_year":"1 वर्ष", "ui.use_it_with_opencode":"OpenCode के साथ उपयोग:", "ui.created":"बनाया गया", "ui.last_used":"अंतिम उपयोग", "ui.actions":"क्रियाएँ", "ui.no_api_keys":"कोई API कुंजी नहीं", "ui.generate_one_above_to_start_sending_requ":"SDK या CLI से अनुरोध भेजना शुरू करने के लिए ऊपर एक बनाएँ।", "ui.administrator":"प्रशासक", "ui.the_single_local_account_that_controls_t":"इस इंस्टॉलेशन को नियंत्रित करने वाला एकमात्र स्थानीय खाता।", "ui.password_was_reset_from_the_command_line":"पासवर्ड कमांड लाइन से रीसेट किया गया", "ui.change_password":"पासवर्ड बदलें", "ui.current_password":"वर्तमान पासवर्ड", "ui.new_password":"नया पासवर्ड", "ui.confirm_new_password":"नया पासवर्ड पुष्टि करें", "ui.update_password":"पासवर्ड अपडेट करें", "ui.signed_in_browsers_for_this_administrato":"इस प्रशासक के साइन-इन किए ब्राउज़र। सत्र 12 घंटे या 60 मिनट निष्क्रियता के बाद समाप्त होते हैं।", "ui.log_out_all_other_sessions":"अन्य सभी सत्र लॉग आउट करें", "ui.device":"डिवाइस", "ui.last_active":"अंतिम सक्रिय", "ui.local_recovery":"स्थानीय रिकवरी", "ui.password_recovery_is_local_only_by_desig":"पासवर्ड रिकवरी जानबूझकर केवल स्थानीय है — कोई ईमेल रीसेट नहीं और कोई सार्वजनिक एंडपॉइंट नहीं जो पासवर्ड बदल सके।", "ui.open_a_shell_where_geekcubo_runs_host_or":"वह शेल खोलें जहाँ GeekCubo चलता है (होस्ट या कंटेनर)।", "ui.choose_a_new_password_at_the_prompt_all_":"प्रॉम्प्ट पर नया पासवर्ड चुनें। सभी डैशबोर्ड सत्र साइन आउट हो जाते हैं; API कुंजियाँ, प्रदाता और उपयोग डेटा अछूते रहते हैं।", "ui.artificial_analysis_api_key":"Artificial Analysis API कुंजी", "ui.optional":"(वैकल्पिक)", "ui.save_key":"कुंजी सहेजें", "ui.remove_stored_key":"संग्रहीत कुंजी हटाएँ", "ui.how_quality_scoring_works":"गुणवत्ता स्कोरिंग कैसे काम करती है", "ui.paste_it_above_and_save_it_is_encrypted_":"इसे ऊपर पेस्ट करें और सहेजें। यह संग्रहण में एन्क्रिप्ट होती है, और पहले से कैश सामग्री हटा दी जाती है ताकि अगला रीफ़्रेश नई कुंजी का उपयोग करे।", "ui.quality_scores":"गुणवत्ता स्कोर", "ui.where_these_numbers_come_from":"ये संख्याएँ कहाँ से आती हैं", "ui.manual":"मैनुअल", "ui.effective":"प्रभावी", "ui.m_blended":"$/M संयुक्त", "ui.help_and_docs":"सहायता और दस्तावेज़", "ui.what_is_geekcubo":"GeekCubo क्या है?", "ui.60_second_quickstart":"60 सेकंड की त्वरित शुरुआत", "ui.keyboard_shortcuts":"कीबोर्ड शॉर्टकट", "ui.switch_tabs":"टैब बदलें", "ui.command_palette":"कमांड पैलेट", "ui.toggle_this_help":"यह सहायता दिखाएँ/छिपाएँ", "ui.close_drawers_palette":"ड्रॉअर / पैलेट बंद करें", "ui.going_further":"आगे", "js.ov_empty_a":"अभी कोई अनुरोध नहीं।", "js.ov_empty_b":"पहला कॉल भेजते ही यह यहाँ दिखेगा।", "js.ra_unavailable":"रूटिंग एनालिटिक्स उपलब्ध नहीं।", "js.no_spend":"इस अवधि में अभी कोई खर्च दर्ज नहीं है।", "js.no_traffic":"अभी कोई ट्रैफ़िक नहीं", "toast.copied":"क्लिपबोर्ड पर कॉपी हुआ", "toast.copy_blocked":"कॉपी नहीं हो सका — ब्राउज़र ने रोक दिया", "toast.signed_in":"{name} के रूप में साइन इन", "toast.admin_created":"प्रशासक {name} बनाया गया", "toast.signed_out":"साइन आउट", "toast.load_providers_failed":"प्रदाता लोड नहीं हुए: {msg}", "toast.removed_provider":"{name} हटाया गया", "toast.api_key_empty":"API कुंजी खाली नहीं हो सकती", "toast.saved_provider":"{name} की कुंजी सहेजी गई", "toast.load_custom_failed":"कस्टम प्रदाता लोड नहीं हुए: {msg}", "toast.updated":"{name} अपडेट हुआ", "toast.model_id_empty":"मॉडल ID खाली नहीं हो सकता", "toast.model_id_dup":"वह मॉडल ID पहले से पंजीकृत है", "toast.model_saved":"मॉडल सहेजा गया", "toast.select_one_model":"कम से कम एक नया मॉडल चुनें", "toast.added_models_one":"1 मॉडल जोड़ा गया", "toast.added_models_many":"{count} मॉडल जोड़े गए", "toast.load_routing_failed":"रूटिंग लोड नहीं हुई: {msg}", "toast.routing_strategy":"रूटिंग रणनीति: {name}", "toast.policy_saved":"रूटिंग नीति सहेजी गई", "toast.load_models_failed":"मॉडल लोड नहीं हुए: {msg}", "toast.load_analytics_failed":"एनालिटिक्स लोड नहीं हुए: {msg}", "toast.load_keys_failed":"कुंजियाँ लोड नहीं हुईं: {msg}", "toast.revoked":"{name} निरस्त हुई", "toast.name_empty":"नाम खाली नहीं हो सकता", "toast.key_renamed":"कुंजी का नाम बदला गया", "toast.name_first":"पहले कुंजी को नाम दें", "toast.created":"{name} बनी", "toast.load_security_failed":"सुरक्षा सेटिंग लोड नहीं हुई: {msg}", "toast.password_updated":"पासवर्ड अपडेट हुआ — अन्य डिवाइस साइन आउट हुए", "toast.load_quality_failed":"गुणवत्ता स्कोर लोड नहीं हुए: {msg}", "toast.score_range":"स्कोर 0 से 100 के बीच की संख्या होनी चाहिए", "toast.override_set":"{name} के लिए ओवरराइड सेट हुआ", "toast.reset":"{name} रीसेट हुआ", "toast.aa_saved":"Artificial Analysis कुंजी सहेजी गई", "toast.stored_removed":"सहेजी गई कुंजी हटाई गई", "toast.remove_key_failed":"कुंजी नहीं हट सकी: {msg}", "toast.aa_refreshed":"Artificial Analysis स्कोर ताज़ा हुए", "toast.refresh_failed":"रिफ़्रेश विफल: {msg}", "toast.load_profiles_failed":"प्रोफ़ाइल लोड नहीं हुई: {msg}", "toast.duplicated":"{name} की प्रतिलिपि बनी", "toast.now_default":"{name} अब डिफ़ॉल्ट है", "toast.deleted":"{name} हटाया गया", "toast.default_reassigned":" — डिफ़ॉल्ट अब auto है", "toast.saved_profile":"{name} सहेजा गया", "toast.file_too_large":"यह फ़ाइल प्रोफ़ाइल निर्यात के लिए बहुत बड़ी है।", "toast.load_integrations_failed":"एकीकरण विकल्प लोड नहीं हुए: {msg}", "toast.load_mi_failed":"मॉडल डेटा स्रोत लोड नहीं हुए: {msg}", "toast.source_added":"स्रोत जोड़ा गया", "toast.legacy_removed":"लीगेसी \"__custom__\" प्रविष्टि हटाई गई", "toast.saved_as":"{name} को {slug} के रूप में सहेजा। नीचे इसके मॉडल लाएँ।", "confirm.remove_provider":"{name} की कुंजी हटाएँ? {name} पर भेजे गए अनुरोध विफल होने लगेंगे।", "confirm.remove_model":"मॉडल {name} हटाएँ?", "confirm.remove_custom":"प्रदाता \"{name}\" और उसके मॉडल हटाएँ?", "confirm.sign_out_others":"इस प्रशासक के अन्य सभी ब्राउज़र साइन आउट करें?", "confirm.reset_score":"{name} को उसके AA स्कोर पर रीसेट करें?", "confirm.remove_aa_key":"सहेजी गई Artificial Analysis कुंजी हटाएँ? पर्यावरण चर में कुंजी हो तो वह फिर लागू होगी।", "confirm.change_slug":"API पहचानकर्ता \"{old}\" से \"{new}\" बदलें?\n\nmodel: \"{old}\" भेजने वाले हर क्लाइंट का काम रुक जाएगा।", "confirm.delete_source":"यह मेटाडेटा स्रोत हटाएँ?", "confirm.legacy_remove":"लीगेसी \"__custom__\" प्रदाता कुंजी ({prefix}) स्थायी रूप से हटाएँ?\n\nयह रूटिंग में उपयोग नहीं होती। अगर अब भी ज़रूरत हो तो कुंजी कहीं और सहेज लें — इसे पुनर्प्राप्त नहीं किया जा सकता।", "confirm.revoke":"\"{name}\" निरस्त करें?\n\nइस कुंजी वाले क्लाइंट को तुरंत 401 मिलेगा। इसे पूर्ववत नहीं किया जा सकता — दोबारा पहुँच चाहिए तो नई कुंजी जारी करें।", "confirm.rotate":"\"{name}\" घुमाएँ?\n\nसमान प्रतिबंधों वाली प्रतिस्थापन कुंजी बनती है और एक बार दिखती है।\n\nOK = पुरानी कुंजी अभी निरस्त करें (तत्काल बदलाव)।\nरद्द = पुरानी कुंजी तब तक रखें जब तक आप स्वयं निरस्त न करें।", "prompt.rename_key":"कुंजी \"{name}\" का नया नाम:", "prompt.set_score":"{name} के लिए मैनुअल गुणवत्ता स्कोर सेट करें (0-100):", "prompt.aa_current":"वर्तमान AA स्कोर: {score}", "prompt.override_note":"वैकल्पिक नोट (ओवरराइड क्यों?):", "auth.session_expired":"सत्र समाप्त हो गया। फिर से साइन इन करें।", "auth.enter_creds":"अपना उपयोगकर्ता नाम और पासवर्ड दर्ज करें।", "auth.creds_required":"उपयोगकर्ता नाम और पासवर्ड आवश्यक हैं।", "auth.pw_mismatch":"पासवर्ड मेल नहीं खाते।", "auth.paste_token":"सर्वर लॉग से एक बार का सेटअप टोकन पेस्ट करें।", "auth.signed_out":"साइन आउट हो गए।", "auth.pw_match":"पासवर्ड मेल खाते हैं।", "auth.pw_mismatch_yet":"पासवर्ड अभी मेल नहीं खाते।", "auth.new_pw_mismatch":"नए पासवर्ड मेल नहीं खाते।", "auth.fill_three":"तीनों फ़ील्ड भरें।", "qa.connection":"Artificial Analysis कनेक्शन", "qa.test":"कनेक्शन जाँचें", "qa.replace":"कुंजी बदलें", "qa.add":"कुंजी जोड़ें", "qa.remove":"कुंजी हटाएँ", "qa.last_sync":"अंतिम सफल सिंक", "qa.last_error":"नवीनतम त्रुटि", "qa.never":"अभी तक सिंक नहीं हुआ", "qa.from_env":"वातावरण से", "qa.saving":"सहेजा जा रहा है…", "qa.key_hint":"इस सर्वर पर एन्क्रिप्ट होकर सहेजी जाती है और दोबारा नहीं दिखती। यह कुंजी सहेजे जाने तक पिछली कुंजी सक्रिय रहती है।", "qa.daily_limit_label":"कुंजी की दैनिक सीमा", "qa.daily_limit_hint":"Artificial Analysis खाता पृष्ठ के अनुसार प्रति 24 घंटे अनुरोध। दस्तावेज़ित 100/दिन के लिए खाली छोड़ें।", "qa.status.not_configured":"कॉन्फ़िगर नहीं", "qa.status.connected":"जुड़ा हुआ", "qa.status.invalid_key":"अमान्य कुंजी", "qa.status.rate_limited":"सीमा पार", "qa.status.connection_failed":"कनेक्शन विफल", "qa.status.cached":"कैश डेटा", "pricing.legend":"मूल्य निर्धारण", "pricing.allow_estimates":"Auto, सबसे सस्ता और लागत सीमाओं में संदर्भ अनुमानों की अनुमति दें", "pricing.allow_estimates_help":"डिफ़ॉल्ट रूप से बंद। केवल पुष्ट प्रदाता कीमतों की तुलना होती है; केवल संदर्भ अनुमान वाले मॉडल Auto से बाहर रहते हैं। चालू होने पर हर अनुमान-आधारित निर्णय चिह्नित होता है।", "confirm.bulk_remove_models":"{count} चयनित मॉडल{plural} हटाएँ? इनके लिए पिन किए अनुरोध विफल होंगे।", "nav.chat":"चैट", "tab.chat.title":"चैट", "tab.chat.sub":"अपने तैनात मॉडलों से बात करें। SDK ट्रैफ़िक की तरह रूटेड, कैश्ड और मीटर्ड।", "ui.open_chat":"चैट खोलें", "ui.open_chat_hint":"ब्राउज़र से अपने तैनात मॉडलों से बात करें — SDK ट्रैफ़िक जैसी ही रूटिंग, कैशिंग और लागत ट्रैकिंग।", "chat.new":"नई चैट", "chat.settings_title":"चैट सेटिंग", "chat.default_title":"नई चैट", "chat.clear_history":"इतिहास मिटाएँ…", "chat.conversations_aria":"बातचीत", "chat.model_aria":"मॉडल", "chat.regenerate":"उत्तर दोबारा बनाएँ", "chat.empty_title":"कुछ भी पूछें।", "chat.empty_sub":"अनुरोध इंजन से रूट होते हैं — SDK ट्रैफ़िक जैसी ही रूटिंग, कैशिंग और लागत ट्रैकिंग।", "chat.input_placeholder":"GeekCubo को संदेश…", "chat.send":"भेजें", "chat.stop":"रोकें", "chat.system_prompt":"सिस्टम प्रॉम्प्ट…", "chat.system_prompt_set":"सिस्टम प्रॉम्प्ट ✓", "chat.system_ph":"आप एक सहायक असिस्टेंट हैं…", "chat.system_help":"खाली = चैट डिफ़ॉल्ट उपयोग करें। प्रति बातचीत सहेजा जाता है।", "chat.save_prompt":"प्रॉम्प्ट सहेजें", "chat.default_model":"डिफ़ॉल्ट मॉडल", "chat.default_model_help":"नई बातचीत के लिए। बातचीत का अपना पिकर इसे ओवरराइड करता है।", "chat.temperature":"टेम्परेचर", "chat.max_tokens":"अधिकतम आउटपुट टोकन", "chat.default_system_prompt":"डिफ़ॉल्ट सिस्टम प्रॉम्प्ट", "chat.default_system_prompt_ph":"आप एक संक्षिप्त इंजीनियरिंग असिस्टेंट हैं।", "chat.default_system_help":"उन बातचीत पर लागू होता है जिनका अपना प्रॉम्प्ट नहीं है।", "chat.save_history":"इस सर्वर पर चैट इतिहास सहेजें", "chat.retention_days":"बातचीत रखें (दिन)", "chat.retention_help":"पुरानी बातचीत हटा दी जाती है। खाली = सब कुछ रखें।", "chat.font_size":"संदेश टेक्स्ट आकार", "chat.fs_small":"छोटा", "chat.fs_medium":"मध्यम", "chat.fs_large":"बड़ा", "chat.enter_to_send":"Enter दबाने पर संदेश भेजें", "chat.privacy_note":"बातचीत इस सर्वर के डेटाबेस में रहती है। अनुरोध आपके कॉन्फ़िगर किए प्रदाताओं को भेजे जाते हैं, बिल्कुल SDK ट्रैफ़िक की तरह।", "chat.privacy_ack":"मैं समझता/समझती हूँ कि चैट ट्रैफ़िक कॉन्फ़िगर किए प्रदाताओं को जाता है", "chat.save_settings":"सेटिंग सहेजें", "chat.model_auto":"ऑटो (राउटर चुनता है)", "chat.no_conversations":"अभी कोई बातचीत नहीं।", "chat.delete_convo_title":"यह बातचीत हटाएँ", "chat.kbd_enter_send":"भेजने के लिए Enter · नई पंक्ति के लिए Shift+Enter", "chat.kbd_ctrl_enter_send":"भेजने के लिए Ctrl+Enter · नई पंक्ति के लिए Enter", "chat.tokens_meta":"इन {in} · आउट {out}", "chat.error_note":"पूरा होने से पहले जनरेशन रुक गया।", "chat.upstream_error":"अपस्ट्रीम मॉडल ने त्रुटि लौटाई।", "toast.chat_load_failed":"चैट डेटा लोड नहीं हुआ: {msg}", "toast.chat_failed":"चैट अनुरोध विफल: {msg}", "toast.chat_convo_deleted":"बातचीत हटाई गई", "toast.chat_cleared":"{count} बातचीत मिटाई गईं", "toast.chat_temp_range":"टेम्परेचर 0 और 2 के बीच होना चाहिए", "toast.chat_settings_saved":"चैट सेटिंग सहेजी गई", "toast.chat_open_convo":"पहले एक बातचीत खोलें", "toast.chat_saved_prompt":"इस बातचीत के लिए सिस्टम प्रॉम्प्ट सहेजा गया", "confirm.delete_conversation":"यह बातचीत हटाएँ?\n\nसंदेश सर्वर डेटाबेस से हट जाएँगे। उपयोग और लागत रिकॉर्ड एनालिटिक्स में बने रहेंगे।", "confirm.clear_chat_history":"सभी सहेजी गई बातचीत हटाएँ?\n\nइस सर्वर पर सहेजे गए सभी चैट संदेश हट जाएँगे। उपयोग और लागत रिकॉर्ड एनालिटिक्स में बने रहेंगे।", "q.ov_score":"मैन्युअल स्कोर (0–100)", "q.ov_note":"नोट", "q.ov_model_ph":"जैसे openai/gpt-4o, anthropic/claude-…", "q.ov_note_ph":"AA स्कोर पर इसका ओवरराइड क्यों", "q.ov_apply":"ओवरराइड लागू करें", "q.ov_clear":"ओवरराइड हटाएँ", "q.ov_help":"एक या अधिक मॉडल आईडी, अल्पविराम से अलग — ओवरराइड सूचीबद्ध हर मॉडल पर लागू होता है। मैन्युअल स्कोर हमेशा AA स्कोर से ऊपर रहते हैं।", "toast.q_ids_required":"कम से कम एक मॉडल आईडी दर्ज करें", "toast.q_too_many":"बल्क में अधिकतम 500 मॉडल आईडी", "toast.q_bulk_set":"{count} मॉडल के लिए ओवरराइड सेट हुआ", "toast.q_bulk_clear":"{count} मॉडल के ओवरराइड हटाए गए", "providers.bulk_actions":"मॉडल के लिए सामूहिक क्रियाएँ", "providers.select_all":"सभी चुनें", "providers.selected_count":"{count} चयनित", "providers.bulk_capability":"क्षमता", "providers.bulk_capability_state":"क्षमता की स्थिति", "providers.cap_tools":"टूल", "providers.cap_vision":"विज़न", "providers.cap_supported":"समर्थित", "providers.cap_unsupported":"असमर्थित", "providers.cap_unknown":"अज्ञात", "providers.cap_catalog":"कैटलॉग उपयोग करें", "providers.cap_json_mode":"JSON मोड", "providers.cap_json_schema":"JSON स्कीमा", "providers.apply":"लागू करें", "providers.enable":"सक्षम करें", "providers.disable":"अक्षम करें", "providers.remove_selected":"चयनित हटाएँ", "providers.resolve_metadata":"मिलान", "toast.metadata_resolved":"मेटाडेटा: {resolved} मिलान, {ambiguous} अस्पष्ट, {unmatched} बेमेल, {failed} विफल।", "select.search_ph":"कैटलॉग कुंजियाँ खोजें…", "providers.catalog_key_ph":"कैटलॉग कुंजियाँ खोजें…", "select.remove_item":"{name} हटाएँ", "select.use_custom":"\"{name}\" का उपयोग करें", "select.no_matches":"कोई मेल खाता मॉडल नहीं", "select.more_results":"{count} और — सीमित करने के लिए टाइप करते रहें", "q.ov_model_search_ph":"मॉडल खोजें और चुनें…", "q.ov_help_picker":"एक या अधिक मॉडल खोजें और चुनें, या नीचे तालिका में पंक्तियाँ चुनें। मैन्युअल स्कोर हमेशा AA स्कोर से ऊपर रहते हैं।", "q.filter_ph":"मॉडल फ़िल्टर करें…", "q.select_filtered":"फ़िल्टर किए गए चुनें", "q.select_all_filtered":"सभी फ़िल्टर किए गए मॉडल चुनें", "q.deselect_all":"सभी अचयनित करें", "q.bulk_set":"चयनित के लिए स्कोर सेट करें", "q.bulk_clear":"चयनित ओवरराइड साफ़ करें", "q.select_model":"{name} चुनें", "confirm.q_bulk_clear":"{count} चयनित मॉडल के मैन्युअल ओवरराइड साफ़ करें?", "qa.daily_limit_short":"दैनिक सीमा", "chat.attach":"फ़ाइलें संलग्न करें", "chat.attach_drop":"संलग्न करने के लिए फ़ाइलें छोड़ें", "chat.attach_remove":"अनुलग्नक हटाएं", "chat.attach_unreadable":"यह फ़ाइल पढ़ी नहीं जा सकी; केवल उसका नाम भेजा जाएगा।", "chat.attach_uploading":"अपलोड हो रहा है…", "chat.attach_too_large":"बहुत बड़ा (अधिकतम {max} MB)", "toast.chat_attach_failed":"{name} संलग्न नहीं कर सके: {msg}", "toast.chat_attach_disabled":"इस सर्वर पर अनुलग्नक अक्षम हैं।", "toast.chat_attach_too_many":"प्रति संदेश अधिकतम {max} अनुलग्नक।", "toast.chat_attach_extract_failed":"{name}: पढ़ा नहीं जा सका ({msg})", "toast.chat_attach_wait":"अपलोड पूरा होने की प्रतीक्षा करें।", "chat.search_toggle":"वेब खोज", "chat.search_settings":"वेब खोज", "chat.search_help":"सक्षम होने पर GeekCubo उत्तर देने से पहले वेब खोजता है और उपयोग किए गए पृष्ठों का हवाला देता है। परिणाम सिस्टम संदेश के रूप में जोड़े जाते हैं, इसलिए कोई भी मॉडल उन्हें उपयोग कर सकता है।", "chat.search_mode":"खोज मोड", "chat.search_mode_off":"बंद", "chat.search_mode_manual":"मैनुअल (प्रति संदेश)", "chat.search_mode_auto":"स्वतः (आरक्षित)", "chat.search_mode_help":"मैनुअल कंपोज़र में एक टॉगल दिखाता है। स्वतः आरक्षित है और अभी लागू नहीं है।", "chat.search_backend":"खोज बैकएंड", "chat.search_backend_none":"बैकएंड चुनें…", "chat.search_backend_searxng":"SearXNG (स्व-होस्टेड)", "chat.search_backend_brave":"Brave खोज API", "chat.search_backend_tavily":"Tavily", "chat.search_url":"SearXNG का URL", "chat.search_url_ph":"http://searxng:8080/", "chat.search_url_help":"आपके SearXNG इंस्टेंस का आधार URL। इंस्टॉलर का search प्रोफ़ाइल इसे आंतरिक नेटवर्क पर उपलब्ध कराता है।", "chat.search_api_key":"API कुंजी", "chat.search_api_key_ph":"सहेजी गई कुंजी बदलने के लिए नई कुंजी चिपकाएँ", "chat.search_key_clear":"सहेजी गई कुंजी हटाएँ", "chat.search_key_help":"इस सर्वर पर एन्क्रिप्टेड संग्रहित, दोबारा नहीं दिखाई जाती। Brave और Tavily के लिए कुंजी आवश्यक है; SearXNG के लिए नहीं।", "chat.search_max_searches":"प्रति बातचीत अधिकतम खोजें", "chat.search_max_results":"प्रति खोज परिणाम", "chat.search_max_fetches":"प्रति खोज लाए जाने वाले पृष्ठ", "chat.search_timeout":"खोज समय-सीमा (सेकंड)", "chat.search_test":"कनेक्शन जाँचें", "chat.search_testing":"जाँच हो रही है…", "chat.search_test_ok":"{ms} मि.से. में {count} परिणाम", "chat.search_test_failed":"खोज जाँच विफल: {msg}", "chat.search_key_state_unset":"कोई कुंजी सहेजी नहीं गई", "chat.search_key_state_set":"कुंजी सहेजी गई", "chat.search_key_state_undecryptable":"सहेजी गई कुंजी डिक्रिप्ट नहीं हो सकती", "chat.context_budget":"संदर्भ: {tokens} / {budget} टोकन", "chat.context_omitted":"{count} पुराने संदेश छोड़े गए", "chat.sources":"स्रोत", "chat.search_used":"वेब खोज: {backend}", "toast.search_saved":"वेब खोज सेटिंग्स सहेजी गईं", "toast.search_save_failed":"वेब खोज सेटिंग्स सहेजी नहीं जा सकीं: {msg}", "toast.search_test_failed":"वेब खोज जाँच विफल रही", "nav.local":"स्थानीय AI", "tab.local.title":"स्थानीय AI", "tab.local.sub":"अपनी ही मशीनों के मॉडल इस राउटर से उपलब्ध कराएँ।", "local.title":"स्थानीय AI कनेक्ट", "local.sub":"अपनी ही मशीनों पर चल रहे मॉडलों तक रूट करें। एक छोटा कनेक्टर इस सर्वर पर बाहर से कनेक्ट होता है, इसलिए कोई पोर्ट नहीं खुलता और किसी इनबाउंड टनल की आवश्यकता नहीं होती।", "local.refresh":"रीफ़्रेश करें", "local.setup_button":"मशीन सेट करें", "local.feature_off_title":"सर्वर पर स्थानीय AI कनेक्ट बंद है", "local.feature_off_body":"सर्वर वातावरण में LOCAL_CONNECT_ENABLED=true सेट करें और पुनः आरंभ करें, फिर यह पृष्ठ पुनः लोड करें।", "local.url_missing_title":"कोई सार्वजनिक URL कॉन्फ़िगर नहीं है", "local.url_missing_body":"LOCAL_CONNECT_PUBLIC_URL को वह पता सेट करें जिस पर कनेक्टर कनेक्ट हो (उदाहरण https://example.com), ताकि इंस्टॉल कमांड और सेवा फ़ाइलें भर जाएँ।", "local.settings_title":"रूटिंग व्यवहार", "local.settings_sub":"नियंत्रित करता है कि स्थानीय मॉडल ऑटो में भाग लें और क्या कोई अनुरोध क्लाउड पर वापस जा सकता है।", "local.set_enabled":"रूटिंग के लिए स्थानीय मशीनें सक्षम करें", "local.set_auto":"ऑटो चयन में स्थानीय मॉडल शामिल करें", "local.set_no_fallback":"स्थानीय मॉडल विफल होने पर कभी क्लाउड पर वापस न जाएँ", "local.settings_help":"स्थानीय मॉडल केवल तब ऑटो के लिए माने जाते हैं जब उनकी कीमत पुष्ट रूप से शून्य हो और मशीन स्वीकृत तथा ऑनलाइन हो। \"कभी वापस न जाएँ\" चालू होने पर केवल-स्थानीय अनुरोध विफल होगा, क्लाउड प्रदाता द्वारा पूरा नहीं किया जाएगा।", "local.save_settings":"सहेजें", "local.settings_saved":"स्थानीय रूटिंग सेटिंग्स सहेजी गईं।", "local.machines_title":"मशीनें", "local.machines_sub":"प्रत्येक मशीन एक कनेक्टर है। लंबित मशीनें दिखती हैं, पर स्वीकृति तक उन पर कुछ नहीं भेजा जाता।", "local.machines_empty":"अभी कोई मशीन नहीं। नामांकन कोड बनाने के लिए \"मशीन सेट करें\" का उपयोग करें।", "local.enrollments_title":"नामांकन कोड", "local.enrollments_sub":"एकबारगी कोड जो कनेक्टर को पंजीकृत होने देते हैं। मशीन के पहली बार कनेक्ट होने पर कोड उपयोग हो जाता है।", "local.new_code":"नया कोड", "local.install_title":"कनेक्टर इंस्टॉल करें", "local.install_sub":"इसे उस मशीन पर चलाएँ जो आपके मॉडल होस्ट करती है (Ollama, LM Studio, vLLM, llama.cpp या कोई भी [OI]-संगत सर्वर)।", "local.service_files":"इसे सेवा के रूप में चलाएँ", "local.delete":"हटाएँ", "local.never":"कभी नहीं", "local.ctx_suffix":"संदर्भ", "local.ctx_unknown":"संदर्भ अज्ञात", "local.no_models":"इस मशीन ने अभी कोई मॉडल नहीं बताया है।", "local.no_enrollments":"कोई नामांकन कोड नहीं।", "local.enroll_active":"सक्रिय", "local.enroll_used":"उपयोग किया गया", "local.status_online":"ऑनलाइन", "local.status_offline":"ऑफ़लाइन", "local.status_pending":"स्वीकृति लंबित", "local.status_approved":"स्वीकृत", "local.status_revoked":"निरस्त", "local.pending_note":"यह मशीन स्वीकृति की प्रतीक्षा में है। मॉडल सूचीबद्ध हैं पर उन पर कुछ नहीं भेजा जाएगा।", "local.action_approve":"स्वीकृत करें", "local.action_discover":"मॉडल खोजें", "local.action_revoke":"निरस्त करें", "local.action_rotate":"क्रेडेंशियल बदलें", "local.action_delete":"हटाएँ", "local.meta_host":"होस्ट नाम", "local.meta_platform":"प्लेटफ़ॉर्म", "local.meta_agent":"कनेक्टर संस्करण", "local.meta_adapters":"एडाप्टर", "local.meta_seen":"अंतिम बार देखा गया", "local.col_model":"मॉडल", "local.col_adapter":"एडाप्टर प्रकार", "local.col_context":"संदर्भ", "local.col_caps":"क्षमताएँ", "local.col_enabled":"सक्षम", "local.kpi_machines":"मशीनें", "local.kpi_online":"अभी ऑनलाइन", "local.kpi_pending":"स्वीकृति लंबित", "local.kpi_models":"मॉडल", "local.toast_approved":"मशीन स्वीकृत हुई।", "local.toast_revoked":"मशीन निरस्त हुई।", "local.toast_deleted":"मशीन हटाई गई।", "local.toast_discovered":"मॉडल सूची रीफ़्रेश हुई।", "local.confirm_revoke":"इस मशीन को निरस्त करें? इसका कनेक्टर तुरंत डिस्कनेक्ट हो जाएगा और क्रेडेंशियल बदलने तक पुनः कनेक्ट नहीं हो सकेगा।", "local.confirm_delete_machine":"इस मशीन और इसकी मॉडल सूची को हटाएँ? इसे पूर्ववत नहीं किया जा सकता।", "local.confirm_rotate":"इस मशीन का क्रेडेंशियल बदलें? चालू कनेक्टर तब तक काम करता रहेगा जब तक वह पुनः कनेक्ट न हो, फिर पुराना क्रेडेंशियल अस्वीकार हो जाएगा।", "local.confirm_delete_enrollment":"यह नामांकन कोड हटाएँ?", "local.credential_once_title":"अभी नया क्रेडेंशियल कॉपी करें", "local.credential_once_body":"यह केवल एक बार दिखाया जाता है। इसे मशीन पर कनेक्टर कॉन्फ़िग में सहेजें।", "local.wizard_title":"स्थानीय मशीन कनेक्ट करें", "local.wizard_close":"बंद करें", "local.wizard_back":"पीछे", "local.wizard_next":"आगे", "local.wizard_done":"पूर्ण", "local.step1":"सक्षम करें", "local.step2":"नामांकन कोड", "local.step3":"इंस्टॉल", "local.step4":"नामांकन", "local.step5":"प्रारंभ", "local.step6":"स्वीकृत करें", "local.step7":"मॉडल", "local.step8":"स्वतः रूटिंग", "local.w0_title":"सुविधा चालू करें", "local.w0_body":"स्थानीय AI कनेक्ट सर्वर-पक्ष की सुविधा है। कनेक्टर पंजीकृत हो सकें, इसके लिए इसे सक्षम करना आवश्यक है।", "local.w0_ready":"सुविधा सक्षम है। नामांकन कोड बनाने के लिए आगे बढ़ें।", "local.w0_blocked":"इस सर्वर पर सुविधा अक्षम है। LOCAL_CONNECT_ENABLED=true सेट करें और पुनः आरंभ करें, फिर यह पृष्ठ पुनः लोड करें।", "local.w1_title":"नामांकन कोड बनाएँ", "local.w1_body":"एकबारगी कोड एक ही कनेक्टर को पंजीकृत होने का अधिकार देता है। यह थोड़े समय बाद समाप्त हो जाता है।", "local.w1_name":"मशीन का नाम (वैकल्पिक)", "local.w1_name_ph":"उदा. office-gpu", "local.w1_name_help":"सूची में इस मशीन को पहचानने के लिए लेबल। आप इसे बाद में बदल सकते हैं।", "local.w1_created":"नामांकन कोड बनाया गया", "local.w2_title":"कनेक्टर पैकेज इंस्टॉल करें", "local.w2_body":"जिस मशीन पर आपके मॉडल हैं, वहाँ कनेक्टर इंस्टॉल करें। Python 3.11 या नया आवश्यक है।", "local.w2_note":"सिस्टम पैकेजों से अलग रखने के लिए इसे वर्चुअल वातावरण में इंस्टॉल करें।", "local.w3_title":"मशीन का नामांकन करें", "local.w3_body":"चरण 2 के कोड के साथ नामांकन कमांड चलाएँ। क्रेडेंशियल कनेक्टर कॉन्फ़िग फ़ाइल में लिखा जाता है।", "local.w3_note":"कोड केवल एक बार उपयोग होता है। समाप्त हो गया हो तो नया बनाएँ।", "local.w4_title":"कनेक्टर प्रारंभ करें", "local.w4_body":"कनेक्ट होते देखने के लिए कनेक्टर को फ़ोरग्राउंड में चलाएँ, फिर इसे सेवा में बदलें।", "local.w4_note":"कनेक्टर एक आउटबाउंड WebSocket खुला रखता है और स्वतः पुनः कनेक्ट होता है।", "local.w5_title":"मशीन के आने की प्रतीक्षा करें", "local.w5_body":"कनेक्टर जुड़ते ही मशीन यहाँ दिखेगी। कुछ समय लगे तो रीफ़्रेश करें।", "local.w5_seen":"{name} जुड़ गई है।", "local.w5_waiting":"अभी कोई मशीन नहीं जुड़ी।", "local.w5_recheck":"फिर जाँचें", "local.w6_title":"मशीन स्वीकृत करें", "local.w6_body":"नई मशीन तब तक लंबित रहती है जब तक कोई प्रशासक स्वीकृत न करे। तब तक उस पर कुछ नहीं भेजा जाता।", "local.w6_none":"स्वीकृत करने के लिए अभी कोई मशीन नहीं।", "local.w6_must_approve":"आगे बढ़ने से पहले लंबित मशीन स्वीकृत करें।", "local.w7_title":"ऑटो में स्थानीय मॉडल सक्षम करें", "local.w7_body":"\"ऑटो चयन में स्थानीय मॉडल शामिल करें\" चालू करें और जिन मॉडलों पर रूट करना है उन्हें सक्षम करें। स्थानीय मॉडल तभी ऑटो के लिए चुने जाते हैं जब उनकी कीमत पुष्ट रूप से शून्य हो।", "local.w7_done":"सेटअप पूरा हुआ। स्थानीय मॉडल अब प्रदाता और रूटिंग पृष्ठों में दिखते हैं।" },
  es: { "q.tabs_label":"Secciones de calidad", "q.tab_models":"Modelos", "q.tab_scores":"Puntuaciones de calidad", "q.tab_aa":"Conexión con Artificial Analysis", "q.col_availability":"Disponibilidad", "q.avail_yes":"disponible", "q.avail_no":"sin clave de proveedor", "q.avail_no_title":"Ninguna clave de proveedor configurada sirve este modelo. Tener datos de benchmark no hace que un modelo sea desplegable.", "q.sync_title":"Sincronización de benchmarks", "q.sync_last_ok":"Última sincronización correcta", "q.sync_last_attempt":"Último intento", "q.sync_returned":"Modelos devueltos por AA", "q.sync_matched":"Coinciden con el catálogo", "q.sync_unmatched":"Sin coincidencia", "q.sync_overrides":"Ajustes manuales", "q.sync_outcome_ok":"correcto", "q.sync_outcome_failed":"fallido", "q.sync_need_key":"Añade una clave en la pestaña Artificial Analysis para sincronizar las puntuaciones. Los ajustes manuales funcionan sin clave.", "q.sync_never":"Aún no se ha sincronizado con esta clave. Usa Actualizar desde AA.", "q.sync_no_models":"La última sincronización no devolvió modelos.", "q.status_line":"{matched} modelos con datos de benchmark · {overrides} ajustes manuales", "q.src.live":"en vivo", "q.src.stale_cache":"en caché (AA inaccesible)", "q.src.stale_db":"en caché (instantánea guardada)", "q.src.error":"sincronización fallida", "q.src.missing_key":"sin clave de API", "q.auto_status":"Estado del enrutamiento automático", "q.auto_status_hint":"Qué elegiría model=\"auto\" ahora mismo. Depende de los proveedores configurados, no de la sincronización de benchmarks.", "q.auto_no_provider":"Ningún modelo desplegable cumple los requisitos actuales. Añade una clave en la página Proveedores. Esto es independiente de la sincronización con Artificial Analysis.", "qa.credential":"Clave de API", "qa.cred_stored":"Guardada en este servidor (cifrada)", "qa.cred_env":"Desde el entorno del servidor", "qa.last_test":"Última prueba de conexión", "qa.last_test_ok":"Última prueba correcta", "qa.not_tested":"Aún sin probar", "qa.sync_status":"Sincronización", "qa.tier":"plan {tier}", "qa.troubleshooting":"Solución de problemas de conexión", "qa.status.key_configured":"Clave configurada", "qa.sync.not_configured":"Sin configurar", "qa.sync.never_synced":"Nunca sincronizado", "qa.sync.synced":"Sincronizado", "qa.sync.sync_failed":"Sincronización fallida", "qa.err.invalid_key":"Clave no válida", "qa.err.insufficient_tier":"El plan no incluye el endpoint", "qa.err.endpoint_retired":"Endpoint retirado", "qa.err.rate_limited":"Límite de solicitudes", "qa.err.timeout":"Tiempo agotado", "qa.err.malformed_response":"Respuesta inesperada", "qa.err.no_data":"No se devolvieron modelos", "qa.err.no_catalog_match":"Sin coincidencias en el catálogo", "qa.err.server_error":"Error del servidor de AA", "qa.err.connection_failed":"Error de conexión", "auth.tagline":"Una pasarela. Todos los modelos de IA.", "auth.welcome":"Bienvenido de nuevo", "auth.subtitle":"Inicia sesión en la consola de administrador de esta instalación de GeekCubo.", "auth.api_key":"Clave API", "auth.continue":"Continuar", "nav.search":"Buscar", "nav.overview":"Resumen", "nav.providers":"Proveedores", "nav.routing":"Enrutamiento", "nav.analytics":"Analíticas", "nav.api_keys":"Claves API", "nav.help_docs":"Ayuda y documentación", "nav.sign_out":"Cerrar sesión", "status.connected":"Conectado", "status.disconnected":"Desconectado", "auth.checking":"Verificando…", "auth.welcome_aboard":"Bienvenido.", "auth.key_invalid":"Esa clave no funcionó. Verifica el prefijo sk-geek-…", "tab.overview.title":"Resumen", "tab.overview.sub":"Tu enrutador LLM de inquilino único de un vistazo.", "tab.providers.title":"Claves de proveedor", "tab.providers.sub":"BYOK — cifradas en reposo, usadas para llamar a LLMs upstream.", "tab.routing.title":"Enrutamiento", "tab.routing.sub":"Cómo model='auto' elige el modelo adecuado para cada solicitud.", "tab.analytics.title":"Analíticas", "tab.analytics.sub":"Gasto, latencia e historial de solicitudes solo local.", "tab.keys.title":"Claves API", "tab.keys.sub":"Claves sk-geek-* que autentican tráfico de inferencia de SDK y CLI.", "nav.quality":"Calidad", "tab.quality.title":"Puntuaciones de calidad", "tab.quality.sub":"Puntuaciones de referencia reales para la estrategia de enrutamiento por calidad. Obtenidas de Artificial Analysis.", "auth.username":"Usuario", "auth.password":"Contraseña", "auth.sign_in":"Iniciar sesión", "nav.security":"Seguridad", "tab.security.title":"Seguridad", "tab.security.sub":"Cuenta de administrador, contraseña y sesiones.", "tab.profiles.title":"Perfiles de enrutamiento", "tab.profiles.sub":"Configuraciones Auto con nombre que los clientes eligen por id de modelo.", "tab.integrations.title":"Conectar una herramienta", "tab.integrations.sub":"Configuración lista para usar en OpenCode, Claude Code, Cursor y más.", "tab.intelligence.title":"Datos de modelos", "tab.intelligence.sub":"De dónde vienen los precios y los límites de los modelos.", "auth.loading":"Cargando…", "auth.checking_status":"Verificando el estado del administrador.", "auth.signin_title":"Iniciar sesión", "auth.signin_sub":"Acceso de administrador a esta instalación de GeekCubo.", "auth.forgot":"¿Olvidaste tu contraseña?", "auth.reset_hint":"Restablécela en el host o el contenedor:", "auth.reset_note":"Las claves, los proveedores y el uso no se ven afectados.", "auth.setup_title":"Crear cuenta de administrador", "auth.setup_sub":"Controla esta instalación de GeekCubo: credenciales de proveedores, claves API y enrutamiento.", "auth.min_password":"Mínimo 8 caracteres", "auth.confirm_password":"Confirmar contraseña", "auth.setup_token":"Token de configuración", "auth.from_log":"Del registro del servidor", "auth.create_admin":"Crear administrador", "auth.where_token":"¿Dónde está el token de configuración?", "auth.token_hint":"Se imprime en el registro del servidor al iniciar por primera vez. Para emitir uno nuevo:", "auth.toggle_password":"Mostrar u ocultar la contraseña", "ov.spend":"Gasto (7 d)", "ov.savings":"Ahorro por enrutamiento", "ov.p50":"latencia p50", "ov.models":"Modelos desplegables", "ov.quickstart":"Inicio rápido", "ov.recent":"Actividad reciente", "prov.title":"Claves de proveedor", "prov.tab_std":"Proveedores estándar", "prov.tab_custom":"Proveedores personalizados", "routing.strategy":"Estrategia de enrutamiento", "routing.pools":"Grupos de modelos", "routing.advanced":"Respaldo, escalado y continuidad", "routing.explain":"Probar una decisión de enrutamiento", "profiles.title":"Perfiles de enrutamiento", "int.title":"Conecta tu herramienta de IA", "md.title":"Fuentes de datos de modelos", "md.lookup":"Consulta de precios", "an.spend":"Gasto por modelo", "an.latency":"Latencia por proveedor", "an.recent":"Solicitudes recientes", "keys.title":"Claves API del enrutador", "sec.sessions":"Sesiones", "q.setup":"Configurar la puntuación de calidad", "q.models":"Modelos", "preset.heading":"Empezar con una plantilla", "preset.sub":"Las plantillas abren el editor ya rellenado: ajústalo antes de guardar.", "preset.economy":"El modelo capaz más barato para cada solicitud. Menor gasto, sin mínimo de calidad.", "preset.premium":"Primero los modelos más potentes, sin mirar el precio. Para trabajo donde manda la calidad.", "preset.coding":"Las llamadas a herramientas y los prompts largos van al grupo Hard. Para agentes y editores.", "preset.fast":"Enrutamiento equilibrado que prefiere menor latencia en el grupo.", "ui.profiles":"Perfiles", "ui.security":"Seguridad", "ui.api_keys":"Claves API", "ui.connect_a_tool":"Conectar una herramienta", "ui.model_data":"Datos de modelos", "ui.connecting":"Conectando…", "ui.language":"Idioma", "ui.light":"Claro", "ui.system":"Sistema", "ui.dark":"Oscuro", "ui.openai_compatible_base_url":"URL base compatible con OpenAI", "ui.copy":"Copiar", "ui.use_this_in_any_openai_compatible_client":"Úsala en cualquier cliente compatible con OpenAI.", "ui.signed_in":"Sesión iniciada", "ui.security_and_sessions":"Seguridad y sesiones", "ui.api_keys_2":"Claves API", "ui.sign_out":"Cerrar sesión", "ui.you_re_up_point_any_openai_sdk_at_your_b":"Ya está listo: apunta cualquier SDK de OpenAI a tu URL base.", "ui.last_5_requests_routed_through_this_serv":"Últimas 5 solicitudes enrutadas por este servidor.", "ui.view_all":"Ver todas", "ui.no_requests_yet":"Aún no hay solicitudes.", "ui.new_here_get_fully_set_up_in_2_minutes":"¿Primera vez? Configúralo todo en 2 minutos", "ui.re_enter_as_a_named_provider":"Reintroducir como proveedor con nombre", "ui.remove_legacy_entry":"Eliminar entrada heredada", "ui.provider":"Proveedor", "ui.others_openai_format":"Otros (formato OpenAI)", "ui.api_key":"Clave API", "ui.provider_name":"Nombre del proveedor", "ui.display_name_a_unique_internal_slug_is_d":"Nombre visible. El slug interno único se deriva automáticamente.", "ui.api_base_url":"URL base de la API", "ui.usually_ends_in_v1_must_be_https_unless_":"Normalmente termina en /v1. Debe ser https salvo que el host esté en CUSTOM_PROVIDER_ALLOWED_LOCAL_HOSTS.", "ui.api_key_2":"Clave API", "ui.encrypted_at_rest_never_displayed_again_":"Cifrada en reposo. Nunca se vuelve a mostrar tras guardarla.", "ui.prefix":"Prefijo", "ui.status":"Estado", "ui.no_provider_keys_yet":"Aún no hay claves de proveedor", "ui.add_at_least_one_to_start_routing_real_t":"Añade al menos una para empezar a enrutar tráfico real. Elige un proveedor arriba o pulsa una sugerencia rápida.", "ui.lowest_cost_that_clears_your_quality_flo":"El coste más bajo que supera tu umbral de calidad. Opción segura con cualquier número de proveedores.", "ui.recommended":"Recomendado", "ui.lowest_per_token_cost_meeting_the_reques":"El coste por token más bajo que cumple las capacidades de la solicitud. La calidad de salida puede variar.", "ui.highest_score_from_artificial_analysis_o":"La puntuación más alta de Artificial Analysis o de tus anulaciones manuales. Sin puntuaciones recurre al precio como aproximación.", "ui.re_ranks_by_observed_success_rate_and_la":"Reordena por tasa de éxito y latencia observadas cuando cada modelo suma 20+ solicitudes aquí. Hasta entonces: Equilibrado.", "ui.sends_each_request_to_your_mundane_or_ha":"Envía cada solicitud a tu grupo Mundane o Hard según señales observables (herramientas, tamaño, longitud).", "ui.highest_throughput_and_lowest_first_toke":"El mayor rendimiento y la menor latencia del primer token según datos de referencia. Se mantiene por compatibilidad.", "ui.legacy":"Heredado", "ui.registered_models":"Modelos registrados", "ui.show":"Mostrar", "ui.deployable":"Desplegables", "ui.custom_providers":"Proveedores personalizados", "ui.model":"Modelo", "ui.capabilities":"Capacidades", "ui.context":"Contexto", "ui.price_1m_in_out":"Precio /1M (ent · sal)", "ui.availability":"Disponibilidad", "ui.pools":"Grupos", "ui.previous":"Anterior", "ui.next":"Siguiente", "ui.fallback_and_escalation_always_keep_the_":"El respaldo y la escalada siempre conservan las capacidades requeridas por la solicitud. Las decisiones se toman antes de empezar; los modelos nunca cambian a mitad de flujo.", "ui.maximum_attempts_primary_fallbacks":"Intentos máximos (principal + respaldos)", "ui.what_counts_as_retryable":"Qué cuenta como reintentable", "ui.quality_floor_percentile_0_off":"Umbral de calidad (percentil, 0 = desactivado)", "ui.needs_quality_scores_ignored_and_reporte":"Necesita puntuaciones de calidad; se ignora (y se indica) si no hay ninguna.", "ui.what_the_quality_floor_does":"Qué hace el umbral de calidad", "ui.balanced_weighs_price_against_quality_th":"Equilibrado sopesa precio y calidad. El umbral excluye los modelos por debajo de ese percentil, así que un modelo muy barato pero débil no puede ganar. Pon 0 para desactivarlo por completo.", "ui.messages":"Mensajes ≥", "ui.prompt_characters":"Caracteres del prompt ≥", "ui.how_request_signals_are_measured":"Cómo se miden las señales de la solicitud", "ui.mode":"Modo", "ui.off":"Desactivado", "ui.manual_client_sends_x_geek_escalate":"Manual (el cliente envía x-geek-escalate)", "ui.auto_after_repeated_upstream_failures":"Automático (tras fallos repetidos del proveedor)", "ui.failures_before_escalating":"Fallos antes de escalar", "ui.max_escalations_per_conversation":"Máximo de escalados por conversación", "ui.destination_pool":"Grupo de destino", "ui.when_escalation_triggers":"Cuándo se activa el escalado", "ui.remember_for_minutes":"Recordar durante (minutos)", "ui.what_continuity_does":"Qué hace la continuidad", "ui.save_routing_policy":"Guardar política de enrutamiento", "ui.dry_run_shows_which_model_auto_would_cho":"Simulación: muestra qué modelo elegiría Auto y por qué. No se envía nada al proveedor.", "ui.messages_2":"Mensajes", "ui.prompt_chars":"Caracteres del prompt", "ui.explain":"Explicar", "ui.three_filters_applied_in_order":"Tres filtros, aplicados en orden.", "ui.how_each_strategy_maps_to_litellm_router":"Cómo se asigna cada estrategia a LiteLLM Router", "ui.strategy":"Estrategia", "ui.import_json":"Importar JSON", "ui.new_profile":"Nuevo perfil", "ui.generates_configuration_that_points_a_cl":"Genera configuración que apunta un cliente a este GeekCubo. Las claves se referencian por variable de entorno, nunca se incrustan.", "ui.search_tools":"Buscar herramientas", "ui.routing_profile_or_model":"Perfil de enrutamiento o modelo", "ui.endpoint":"Endpoint", "ui.format":"Formato", "ui.download":"Descargar", "ui.add_source":"Añadir fuente", "ui.name":"Nombre", "ui.https_url_models_dev_compatible_json":"URL HTTPS (JSON compatible con models.dev)", "ui.save_source":"Guardar fuente", "ui.cancel":"Cancelar", "ui.shows_what_each_enabled_source_reports_f":"Muestra lo que reporta cada fuente activa para un modelo y qué valor usaría GeekCubo. Tus precios configurados siempre ganan.", "ui.look_up":"Consultar", "ui.routing":"Enrutamiento", "ui.volume":"Volumen", "ui.routing_decisions":"Decisiones de enrutamiento", "ui.how_auto_requests_were_classified_and_wh":"Cómo se clasificaron las solicitudes Auto y a dónde fueron.", "ui.by_tier":"Por grupo", "ui.by_strategy":"Por estrategia", "ui.by_routing_id":"Por id de enrutamiento", "ui.top_models_served":"Modelos más servidos", "ui.reliability":"Confiabilidad", "ui.errors_by_cause":"Errores por causa", "ui.compare_against_a_baseline_model":"Comparar con un modelo de referencia", "ui.none":"Ninguno", "ui.compare":"Comparar", "ui.how_the_comparison_is_calculated":"Cómo se calcula la comparación", "ui.p50_and_p99_sourced_from_local_request_l":"p50 y p99 — provenientes de los registros locales de solicitudes.", "ui.requests":"Solicitudes", "ui.newest_first_click_a_row_to_copy_its_tra":"Más recientes primero. Haz clic en una fila para copiar su trace ID.", "ui.when":"Cuándo", "ui.tokens_in_out":"Tokens (ent / sal)", "ui.latency":"Latencia", "ui.no_traffic_yet":"Aún no hay tráfico", "ui.once_you_start_sending_requests_they_ll_":"Cuando empieces a enviar solicitudes, aparecerán aquí en tiempo real.", "ui.expires":"Caduca", "ui.never":"Nunca", "ui.7_days":"7 días", "ui.30_days":"30 días", "ui.90_days":"90 días", "ui.1_year":"1 año", "ui.use_it_with_opencode":"Úsala con OpenCode:", "ui.created":"Creada", "ui.last_used":"Último uso", "ui.actions":"Acciones", "ui.no_api_keys":"No hay claves API", "ui.generate_one_above_to_start_sending_requ":"Genera una arriba para empezar a enviar solicitudes desde un SDK o la CLI.", "ui.administrator":"Administrador", "ui.the_single_local_account_that_controls_t":"La única cuenta local que controla esta instalación.", "ui.password_was_reset_from_the_command_line":"La contraseña se restableció desde la línea de comandos", "ui.change_password":"Cambiar contraseña", "ui.current_password":"Contraseña actual", "ui.new_password":"Nueva contraseña", "ui.confirm_new_password":"Confirmar nueva contraseña", "ui.update_password":"Actualizar contraseña", "ui.signed_in_browsers_for_this_administrato":"Navegadores con sesión iniciada para este administrador. Las sesiones caducan tras 12 horas, o 60 minutos inactivas.", "ui.log_out_all_other_sessions":"Cerrar sesión en todos los demás", "ui.device":"Dispositivo", "ui.last_active":"Última actividad", "ui.local_recovery":"Recuperación local", "ui.password_recovery_is_local_only_by_desig":"La recuperación de contraseña es solo local por diseño: no hay restablecimiento por correo ni endpoint público que pueda cambiarla.", "ui.open_a_shell_where_geekcubo_runs_host_or":"Abre una shell donde se ejecute GeekCubo (host o contenedor).", "ui.choose_a_new_password_at_the_prompt_all_":"Elige una nueva contraseña en el indicador. Se cierran todas las sesiones del panel; las claves API, los proveedores y el uso no se tocan.", "ui.artificial_analysis_api_key":"Clave API de Artificial Analysis", "ui.optional":"(opcional)", "ui.save_key":"Guardar clave", "ui.remove_stored_key":"Eliminar clave guardada", "ui.how_quality_scoring_works":"Cómo funciona la puntuación de calidad", "ui.paste_it_above_and_save_it_is_encrypted_":"Pégala arriba y guarda. Se cifra en reposo y lo ya cacheado se descarta para que la próxima actualización use la nueva clave.", "ui.quality_scores":"Puntuaciones de calidad", "ui.where_these_numbers_come_from":"De dónde vienen estos números", "ui.manual":"Manual", "ui.effective":"Efectiva", "ui.m_blended":"$/M combinado", "ui.help_and_docs":"Ayuda y documentación", "ui.what_is_geekcubo":"¿Qué es GeekCubo?", "ui.60_second_quickstart":"Inicio rápido en 60 segundos", "ui.keyboard_shortcuts":"Atajos de teclado", "ui.switch_tabs":"Cambiar de pestaña", "ui.command_palette":"Paleta de comandos", "ui.toggle_this_help":"Mostrar u ocultar esta ayuda", "ui.close_drawers_palette":"Cerrar paneles / paleta", "ui.going_further":"Más allá", "js.ov_empty_a":"Aún no hay solicitudes.", "js.ov_empty_b":"Cuando envíes tu primera llamada, aparecerá aquí.", "js.ra_unavailable":"Analíticas de enrutamiento no disponibles.", "js.no_spend":"Aún no hay gasto registrado en este periodo.", "js.no_traffic":"Aún no hay tráfico", "toast.copied":"Copiado al portapapeles", "toast.copy_blocked":"No se pudo copiar — tu navegador lo bloqueó", "toast.signed_in":"Sesión iniciada como {name}", "toast.admin_created":"Administrador {name} creado", "toast.signed_out":"Sesión cerrada", "toast.load_providers_failed":"No se pudieron cargar los proveedores: {msg}", "toast.removed_provider":"Eliminado {name}", "toast.api_key_empty":"La clave API no puede estar vacía", "toast.saved_provider":"Clave de {name} guardada", "toast.load_custom_failed":"No se pudieron cargar los proveedores personalizados: {msg}", "toast.updated":"Actualizado {name}", "toast.model_id_empty":"El ID del modelo no puede estar vacío", "toast.model_id_dup":"Ese ID de modelo ya está registrado", "toast.model_saved":"Modelo guardado", "toast.select_one_model":"Selecciona al menos un modelo nuevo", "toast.added_models_one":"1 modelo añadido", "toast.added_models_many":"{count} modelos añadidos", "toast.load_routing_failed":"No se pudo cargar el enrutamiento: {msg}", "toast.routing_strategy":"Estrategia de enrutamiento: {name}", "toast.policy_saved":"Política de enrutamiento guardada", "toast.load_models_failed":"No se pudieron cargar los modelos: {msg}", "toast.load_analytics_failed":"No se pudieron cargar las analíticas: {msg}", "toast.load_keys_failed":"No se pudieron cargar las claves: {msg}", "toast.revoked":"Revocada {name}", "toast.name_empty":"El nombre no puede estar vacío", "toast.key_renamed":"Clave renombrada", "toast.name_first":"Ponle un nombre a la clave primero", "toast.created":"Creada {name}", "toast.load_security_failed":"No se pudo cargar la seguridad: {msg}", "toast.password_updated":"Contraseña actualizada — se cerró la sesión en otros dispositivos", "toast.load_quality_failed":"No se pudieron cargar las puntuaciones: {msg}", "toast.score_range":"La puntuación debe ser un número entre 0 y 100", "toast.override_set":"Anulación aplicada a {name}", "toast.reset":"Restablecido {name}", "toast.aa_saved":"Clave de Artificial Analysis guardada", "toast.stored_removed":"Clave guardada eliminada", "toast.remove_key_failed":"No se pudo eliminar la clave: {msg}", "toast.aa_refreshed":"Puntuaciones de Artificial Analysis actualizadas", "toast.refresh_failed":"Error al actualizar: {msg}", "toast.load_profiles_failed":"No se pudieron cargar los perfiles: {msg}", "toast.duplicated":"Duplicado {name}", "toast.now_default":"{name} ahora es el predeterminado", "toast.deleted":"Eliminado {name}", "toast.default_reassigned":" — el predeterminado ahora es auto", "toast.saved_profile":"Guardado {name}", "toast.file_too_large":"Ese archivo es demasiado grande para ser una exportación de perfil.", "toast.load_integrations_failed":"No se pudieron cargar las integraciones: {msg}", "toast.load_mi_failed":"No se pudieron cargar las fuentes de datos: {msg}", "toast.source_added":"Fuente añadida", "toast.legacy_removed":"Entrada heredada \"__custom__\" eliminada", "toast.saved_as":"Guardado {name} como {slug}. Obtén sus modelos abajo.", "confirm.remove_provider":"¿Eliminar la clave de {name}? Las solicitudes dirigidas a {name} empezarán a fallar.", "confirm.remove_model":"¿Eliminar el modelo {name}?", "confirm.remove_custom":"¿Eliminar el proveedor \"{name}\" y sus modelos?", "confirm.sign_out_others":"¿Cerrar sesión en todos los demás navegadores de este administrador?", "confirm.reset_score":"¿Restablecer {name} a su puntuación de AA?", "confirm.remove_aa_key":"¿Eliminar la clave guardada de Artificial Analysis? Si hay una clave en el entorno, volverá a usarse.", "confirm.change_slug":"¿Cambiar el identificador de API de \"{old}\" a \"{new}\"?\n\nTodo cliente que envíe model: \"{old}\" dejará de funcionar.", "confirm.delete_source":"¿Eliminar esta fuente de metadatos?", "confirm.legacy_remove":"¿Eliminar permanentemente la clave de proveedor heredada \"__custom__\" ({prefix})?\n\nNo se usa para enrutar. Asegúrate de tener la clave guardada en otro sitio si aún la necesitas — no se puede recuperar.", "confirm.revoke":"¿Revocar \"{name}\"?\n\nLos clientes que usan esta clave reciben 401 de inmediato. No se puede deshacer — emite una nueva clave si vuelves a necesitar acceso.", "confirm.rotate":"¿Rotar \"{name}\"?\n\nSe crea una clave de reemplazo con las mismas restricciones y se muestra una sola vez.\n\nAceptar = revocar la clave anterior ahora (corte inmediato).\nCancelar = mantener la clave anterior hasta que la revoques tú.", "prompt.rename_key":"Renombrar la clave \"{name}\" a:", "prompt.set_score":"Establecer puntuación de calidad manual para {name} (0-100):", "prompt.aa_current":"La puntuación de AA es actualmente: {score}", "prompt.override_note":"Nota opcional (¿por qué la anulas?):", "auth.session_expired":"Tu sesión expiró. Vuelve a iniciar sesión.", "auth.enter_creds":"Introduce tu usuario y contraseña.", "auth.creds_required":"Se requieren usuario y contraseña.", "auth.pw_mismatch":"Las contraseñas no coinciden.", "auth.paste_token":"Pega el token de configuración de un solo uso del registro del servidor.", "auth.signed_out":"Sesión cerrada.", "auth.pw_match":"Las contraseñas coinciden.", "auth.pw_mismatch_yet":"Las contraseñas aún no coinciden.", "auth.new_pw_mismatch":"Las contraseñas nuevas no coinciden.", "auth.fill_three":"Rellena los tres campos.", "qa.connection":"Conexión con Artificial Analysis", "qa.test":"Probar conexión", "qa.replace":"Reemplazar clave", "qa.add":"Añadir clave", "qa.remove":"Eliminar clave", "qa.last_sync":"Última sincronización correcta", "qa.last_error":"Último error", "qa.never":"aún sin sincronizar", "qa.from_env":"del entorno", "qa.saving":"Guardando…", "qa.key_hint":"Se cifra en este servidor y nunca se vuelve a mostrar. La clave anterior sigue activa hasta guardar esta.", "qa.daily_limit_label":"Límite diario de tu clave", "qa.daily_limit_hint":"Solicitudes por 24 horas, según tu página de cuenta de Artificial Analysis. Déjalo en blanco para usar el límite documentado de 100/día.", "qa.status.not_configured":"No configurada", "qa.status.connected":"Conectada", "qa.status.invalid_key":"Clave no válida", "qa.status.rate_limited":"Límite alcanzado", "qa.status.connection_failed":"Error de conexión", "qa.status.cached":"Datos en caché", "pricing.legend":"Precios", "pricing.allow_estimates":"Permitir estimaciones de referencia en Auto, Más barato y límites de coste", "pricing.allow_estimates_help":"Desactivado por defecto. Solo se comparan precios confirmados del proveedor; los modelos con solo una estimación de referencia quedan fuera de Auto. Si se activa, cada decisión basada en estimaciones se etiqueta.", "confirm.bulk_remove_models":"¿Eliminar {count} modelo(s) seleccionado(s)? Las solicitudes fijadas hacia ellos fallarán.", "nav.chat":"Chats", "tab.chat.title":"Chats", "tab.chat.sub":"Habla con tus modelos desplegados. Enrutado, cacheado y medido como el tráfico de SDK.", "ui.open_chat":"Abrir chat", "ui.open_chat_hint":"Chatea con tus modelos desplegados desde el navegador — mismo enrutamiento, caché y registro de costos que el tráfico SDK.", "chat.new":"Nuevo chat", "chat.settings_title":"Ajustes de chat", "chat.default_title":"Nuevo chat", "chat.clear_history":"Borrar historial…", "chat.conversations_aria":"Conversaciones", "chat.model_aria":"Modelo", "chat.regenerate":"Regenerar respuesta", "chat.empty_title":"Pregunta lo que quieras.", "chat.empty_sub":"Las solicitudes pasan por el motor — mismo enrutamiento, caché y registro de costos que el tráfico SDK.", "chat.input_placeholder":"Mensaje a GeekCubo…", "chat.send":"Enviar", "chat.stop":"Detener", "chat.system_prompt":"Prompt del sistema…", "chat.system_prompt_set":"Prompt del sistema ✓", "chat.system_ph":"Eres un asistente útil…", "chat.system_help":"Vacío = usar el valor predeterminado del chat. Se guarda por conversación.", "chat.save_prompt":"Guardar prompt", "chat.default_model":"Modelo predeterminado", "chat.default_model_help":"Se usa en conversaciones nuevas. El selector de la propia conversación lo anula.", "chat.temperature":"Temperatura", "chat.max_tokens":"Máx. tokens de salida", "chat.default_system_prompt":"Prompt de sistema predeterminado", "chat.default_system_prompt_ph":"Eres un asistente de ingeniería conciso.", "chat.default_system_help":"Se aplica a conversaciones sin su propio prompt.", "chat.save_history":"Guardar el historial de chat en este servidor", "chat.retention_days":"Conservar conversaciones durante (días)", "chat.retention_help":"Las conversaciones más antiguas se eliminan. Vacío conserva todo.", "chat.font_size":"Tamaño del texto", "chat.fs_small":"Pequeño", "chat.fs_medium":"Mediano", "chat.fs_large":"Grande", "chat.enter_to_send":"Enter envía el mensaje", "chat.privacy_note":"Las conversaciones quedan en la base de datos de este servidor. Las solicitudes se envían a los proveedores que configuraste, igual que el tráfico SDK.", "chat.privacy_ack":"Entiendo que el tráfico de chat va a los proveedores configurados", "chat.save_settings":"Guardar ajustes", "chat.model_auto":"Auto (elige el router)", "chat.no_conversations":"Aún no hay conversaciones.", "chat.delete_convo_title":"Eliminar esta conversación", "chat.kbd_enter_send":"Enter para enviar · Shift+Enter para nueva línea", "chat.kbd_ctrl_enter_send":"Ctrl+Enter para enviar · Enter para nueva línea", "chat.tokens_meta":"{in} entrada · {out} salida", "chat.error_note":"La generación se detuvo antes de completarse.", "chat.upstream_error":"El modelo upstream devolvió un error.", "toast.chat_load_failed":"No se pudieron cargar los datos del chat: {msg}", "toast.chat_failed":"Falló la solicitud de chat: {msg}", "toast.chat_convo_deleted":"Conversación eliminada", "toast.chat_cleared":"Se borraron {count} conversaciones", "toast.chat_temp_range":"La temperatura debe estar entre 0 y 2", "toast.chat_settings_saved":"Ajustes de chat guardados", "toast.chat_open_convo":"Abre primero una conversación", "toast.chat_saved_prompt":"Prompt de sistema guardado para esta conversación", "confirm.delete_conversation":"¿Eliminar esta conversación?\n\nLos mensajes se quitan de la base de datos del servidor. Los registros de uso y costos permanecen en analíticas.", "confirm.clear_chat_history":"¿Eliminar TODAS las conversaciones guardadas?\n\nSe quitan todos los mensajes de chat almacenados en este servidor. Los registros de uso y costos permanecen en analíticas.", "q.ov_score":"Puntuación manual (0–100)", "q.ov_note":"Nota", "q.ov_model_ph":"p. ej. openai/gpt-4o, anthropic/claude-…", "q.ov_note_ph":"Por qué anula la puntuación de AA", "q.ov_apply":"Aplicar anulación", "q.ov_clear":"Quitar anulación", "q.ov_help":"Uno o más ids de modelo, separados por comas — la anulación se aplica a todos los modelos listados. Las puntuaciones manuales siempre ganan a las de AA.", "toast.q_ids_required":"Introduce al menos un id de modelo", "toast.q_too_many":"El lote está limitado a 500 ids de modelo", "toast.q_bulk_set":"Anulación aplicada a {count} modelo(s)", "toast.q_bulk_clear":"Anulaciones eliminadas de {count} modelo(s)", "providers.bulk_actions":"Acciones masivas de modelos", "providers.select_all":"Seleccionar todo", "providers.selected_count":"{count} seleccionados", "providers.bulk_capability":"Capacidad", "providers.bulk_capability_state":"Estado de capacidad", "providers.cap_tools":"Herramientas", "providers.cap_vision":"Visión", "providers.cap_supported":"Compatible", "providers.cap_unsupported":"No compatible", "providers.cap_unknown":"Desconocido", "providers.cap_catalog":"Usar catálogo", "providers.cap_json_mode":"Modo JSON", "providers.cap_json_schema":"Esquema JSON", "providers.apply":"Aplicar", "providers.enable":"Activar", "providers.disable":"Desactivar", "providers.remove_selected":"Quitar seleccionados", "providers.resolve_metadata":"Resolver", "toast.metadata_resolved":"Metadatos: {resolved} resueltos, {ambiguous} ambiguos, {unmatched} sin coincidencia, {failed} fallidos.", "select.search_ph":"Buscar claves de catálogo…", "providers.catalog_key_ph":"Buscar claves de catálogo…", "select.remove_item":"Quitar {name}", "select.use_custom":"Usar «{name}»", "select.no_matches":"No hay modelos coincidentes", "select.more_results":"{count} más: sigue escribiendo para acotar", "q.ov_model_search_ph":"Busca y elige modelos…", "q.ov_help_picker":"Busca y elige uno o más modelos, o marca filas en la tabla de abajo. Las puntuaciones manuales siempre prevalecen sobre las de AA.", "q.filter_ph":"Filtrar modelos…", "q.select_filtered":"Seleccionar filtrados", "q.select_all_filtered":"Seleccionar todos los modelos filtrados", "q.deselect_all":"Deseleccionar todo", "q.bulk_set":"Puntuar seleccionados", "q.bulk_clear":"Borrar ajustes seleccionados", "q.select_model":"Seleccionar {name}", "confirm.q_bulk_clear":"¿Borrar los ajustes manuales de {count} modelos seleccionados?", "qa.daily_limit_short":"Límite diario", "chat.attach":"Adjuntar archivos", "chat.attach_drop":"Suelta archivos para adjuntar", "chat.attach_remove":"Quitar adjunto", "chat.attach_unreadable":"No se pudo leer este archivo; solo se envía su nombre.", "chat.attach_uploading":"Subiendo…", "chat.attach_too_large":"Demasiado grande (máx. {max} MB)", "toast.chat_attach_failed":"No se pudo adjuntar {name}: {msg}", "toast.chat_attach_disabled":"Los adjuntos están desactivados en este servidor.", "toast.chat_attach_too_many":"Como máximo {max} adjuntos por mensaje.", "toast.chat_attach_extract_failed":"{name}: no se pudo leer ({msg})", "toast.chat_attach_wait":"Espera a que terminen las subidas.", "chat.search_toggle":"Búsqueda web", "chat.search_settings":"Búsqueda web", "chat.search_help":"Cuando está activa, GeekCubo busca en la web antes de responder y cita las páginas usadas. Los resultados se inyectan como mensaje de sistema, así que cualquier modelo puede usarlos.", "chat.search_mode":"Modo de búsqueda", "chat.search_mode_off":"Desactivada", "chat.search_mode_manual":"Manual (por mensaje)", "chat.search_mode_auto":"Automática (reservada)", "chat.search_mode_help":"El modo manual muestra un interruptor en el compositor. El automático está reservado y aún no se ha implementado.", "chat.search_backend":"Motor de búsqueda", "chat.search_backend_none":"Elige un motor…", "chat.search_backend_searxng":"SearXNG (autoalojado)", "chat.search_backend_brave":"API de Brave Search", "chat.search_backend_tavily":"Tavily", "chat.search_url":"URL de SearXNG", "chat.search_url_ph":"http://searxng:8080/", "chat.search_url_help":"URL base de tu instancia de SearXNG. El perfil search del instalador la sirve en la red interna.", "chat.search_api_key":"Clave de API", "chat.search_api_key_ph":"Pega una clave nueva para sustituir la guardada", "chat.search_key_clear":"Quitar clave guardada", "chat.search_key_help":"Se guarda cifrada en este servidor y no se vuelve a mostrar. Brave y Tavily requieren clave; SearXNG no.", "chat.search_max_searches":"Máximo de búsquedas por conversación", "chat.search_max_results":"Resultados por búsqueda", "chat.search_max_fetches":"Páginas a descargar por búsqueda", "chat.search_timeout":"Tiempo límite de búsqueda (segundos)", "chat.search_test":"Probar conexión", "chat.search_testing":"Probando…", "chat.search_test_ok":"{count} resultados en {ms} ms", "chat.search_test_failed":"La prueba de búsqueda falló: {msg}", "chat.search_key_state_unset":"Sin clave guardada", "chat.search_key_state_set":"Clave guardada", "chat.search_key_state_undecryptable":"La clave guardada no se puede descifrar", "chat.context_budget":"Contexto: {tokens} / {budget} tokens", "chat.context_omitted":"Se omitieron {count} mensajes anteriores", "chat.sources":"Fuentes", "chat.search_used":"búsqueda web: {backend}", "toast.search_saved":"Ajustes de búsqueda web guardados", "toast.search_save_failed":"No se pudieron guardar los ajustes de búsqueda web: {msg}", "toast.search_test_failed":"La prueba de búsqueda web falló", "nav.local":"IA local", "tab.local.title":"IA local", "tab.local.sub":"Sirve modelos desde tus propias máquinas a través de este enrutador.", "local.title":"Conexión de IA local", "local.sub":"Enruta a modelos que se ejecutan en tus propias máquinas. Un pequeño conector marca hacia este servidor, así que no se abren puertos ni se necesita un túnel entrante.", "local.refresh":"Actualizar", "local.setup_button":"Configurar una máquina", "local.feature_off_title":"La conexión de IA local está desactivada en el servidor", "local.feature_off_body":"Define LOCAL_CONNECT_ENABLED=true en el entorno del servidor y reinicia; luego vuelve a cargar esta página.", "local.url_missing_title":"No hay URL pública configurada", "local.url_missing_body":"Define LOCAL_CONNECT_PUBLIC_URL con la dirección a la que deben marcar los conectores (por ejemplo https://example.com) para que se rellenen el comando de instalación y los archivos de servicio.", "local.settings_title":"Comportamiento del enrutamiento", "local.settings_sub":"Controla si los modelos locales participan en Auto y si una solicitud puede recurrir a la nube.", "local.set_enabled":"Habilitar máquinas locales para el enrutamiento", "local.set_auto":"Incluir modelos locales en la selección automática", "local.set_no_fallback":"Nunca recurrir a la nube cuando falla un modelo local", "local.settings_help":"Los modelos locales solo se consideran para Auto cuando su precio es cero confirmado y la máquina está aprobada y en línea. Con «nunca recurrir» activado, una solicitud solo local falla en lugar de ser atendida por un proveedor en la nube.", "local.save_settings":"Guardar", "local.settings_saved":"Ajustes de enrutamiento local guardados.", "local.machines_title":"Máquinas", "local.machines_sub":"Cada máquina es un conector. Las máquinas pendientes son visibles pero no reciben tráfico hasta que las apruebes.", "local.machines_empty":"Aún no hay máquinas. Usa «Configurar una máquina» para generar un código de inscripción.", "local.enrollments_title":"Códigos de inscripción", "local.enrollments_sub":"Códigos de un solo uso que permiten registrar un conector. Cada código se consume la primera vez que se conecta una máquina.", "local.new_code":"Nuevo código", "local.install_title":"Instalar el conector", "local.install_sub":"Ejecuta esto en la máquina que aloja tus modelos (Ollama, LM Studio, vLLM, llama.cpp o cualquier servidor compatible con [OI]).", "local.service_files":"Ejecutarlo como servicio", "local.delete":"Eliminar", "local.never":"nunca", "local.ctx_suffix":"contexto", "local.ctx_unknown":"contexto desconocido", "local.no_models":"Esta máquina aún no ha informado ningún modelo.", "local.no_enrollments":"No hay códigos de inscripción.", "local.enroll_active":"Activo", "local.enroll_used":"Usado", "local.status_online":"En línea", "local.status_offline":"Sin conexión", "local.status_pending":"Pendiente de aprobación", "local.status_approved":"Aprobada", "local.status_revoked":"Revocada", "local.pending_note":"Esta máquina espera aprobación. Los modelos se listan pero no recibirán tráfico.", "local.action_approve":"Aprobar", "local.action_discover":"Descubrir modelos", "local.action_revoke":"Revocar", "local.action_rotate":"Rotar credencial", "local.action_delete":"Eliminar", "local.meta_host":"Nombre de host", "local.meta_platform":"Plataforma", "local.meta_agent":"Versión del conector", "local.meta_adapters":"Adaptadores", "local.meta_seen":"Visto por última vez", "local.col_model":"Modelo", "local.col_adapter":"Tipo de adaptador", "local.col_context":"Contexto", "local.col_caps":"Capacidades", "local.col_enabled":"Activado", "local.kpi_machines":"Máquinas", "local.kpi_online":"En línea ahora", "local.kpi_pending":"Pendiente de aprobación", "local.kpi_models":"Modelos", "local.toast_approved":"Máquina aprobada.", "local.toast_revoked":"Máquina revocada.", "local.toast_deleted":"Máquina eliminada.", "local.toast_discovered":"Lista de modelos actualizada.", "local.confirm_revoke":"¿Revocar esta máquina? Su conector se desconecta de inmediato y no podrá reconectarse hasta que rotes su credencial.", "local.confirm_delete_machine":"¿Eliminar esta máquina y su lista de modelos? Esto no se puede deshacer.", "local.confirm_rotate":"¿Rotar la credencial de esta máquina? El conector en ejecución sigue funcionando hasta que se reconecte; entonces se rechaza la credencial anterior.", "local.confirm_delete_enrollment":"¿Eliminar este código de inscripción?", "local.credential_once_title":"Copia la nueva credencial ahora", "local.credential_once_body":"Solo se muestra una vez. Guárdala en la configuración del conector en la máquina.", "local.wizard_title":"Conectar una máquina local", "local.wizard_close":"Cerrar", "local.wizard_back":"Atrás", "local.wizard_next":"Siguiente", "local.wizard_done":"Listo", "local.step1":"Activar", "local.step2":"Código de inscripción", "local.step3":"Instalar", "local.step4":"Inscribir", "local.step5":"Iniciar", "local.step6":"Aprobar", "local.step7":"Modelos", "local.step8":"Enrutamiento automático", "local.w0_title":"Activa la función", "local.w0_body":"La conexión de IA local es una función del servidor. Debe estar habilitada antes de que los conectores puedan registrarse.", "local.w0_ready":"La función está habilitada. Continúa para crear un código de inscripción.", "local.w0_blocked":"La función está deshabilitada en este servidor. Define LOCAL_CONNECT_ENABLED=true y reinicia; luego vuelve a cargar esta página.", "local.w1_title":"Crea un código de inscripción", "local.w1_body":"Un código de un solo uso autoriza a un único conector a registrarse. Caduca tras un breve periodo.", "local.w1_name":"Nombre de la máquina (opcional)", "local.w1_name_ph":"p. ej. oficina-gpu", "local.w1_name_help":"Una etiqueta para reconocer esta máquina en la lista. Puedes renombrarla después.", "local.w1_created":"Código de inscripción creado", "local.w2_title":"Instala el paquete del conector", "local.w2_body":"En la máquina que aloja tus modelos, instala el conector. Se requiere Python 3.11 o posterior.", "local.w2_note":"Instálalo en un entorno virtual para mantenerlo aislado de los paquetes del sistema.", "local.w3_title":"Inscribe la máquina", "local.w3_body":"Ejecuta el comando de inscripción con el código del paso 2. La credencial se escribe en el archivo de configuración del conector.", "local.w3_note":"El código es de un solo uso. Si ha caducado, crea uno nuevo.", "local.w4_title":"Inicia el conector", "local.w4_body":"Ejecuta el conector en primer plano para verlo conectar y luego pásalo a un servicio.", "local.w4_note":"El conector mantiene un único WebSocket saliente abierto y se reconecta automáticamente.", "local.w5_title":"Espera a que aparezca la máquina", "local.w5_body":"Cuando el conector se conecte, la máquina aparecerá aquí. Actualiza si tarda un momento.", "local.w5_seen":"{name} se ha conectado.", "local.w5_waiting":"Aún no se ha conectado ninguna máquina.", "local.w5_recheck":"Comprobar de nuevo", "local.w6_title":"Aprueba la máquina", "local.w6_body":"Una máquina nueva permanece pendiente hasta que un administrador la aprueba. Hasta entonces no se le enruta nada.", "local.w6_none":"Todavía no hay ninguna máquina que aprobar.", "local.w6_must_approve":"Aprueba la máquina pendiente antes de continuar.", "local.w7_title":"Habilita modelos locales en Auto", "local.w7_body":"Activa «Incluir modelos locales en la selección automática» y habilita los modelos a los que quieras enrutar. Los modelos locales solo se eligen para Auto cuando su precio es cero confirmado.", "local.w7_done":"La configuración está completa. Los modelos locales ya aparecen en las páginas de Proveedores y Enrutamiento." },
  pt: { "q.tabs_label":"Seções de qualidade", "q.tab_models":"Modelos", "q.tab_scores":"Pontuações de qualidade", "q.tab_aa":"Conexão com Artificial Analysis", "q.col_availability":"Disponibilidade", "q.avail_yes":"disponível", "q.avail_no":"sem chave de provedor", "q.avail_no_title":"Nenhuma chave de provedor configurada atende este modelo. Ter dados de benchmark não torna um modelo implantável.", "q.sync_title":"Sincronização de benchmarks", "q.sync_last_ok":"Última sincronização bem-sucedida", "q.sync_last_attempt":"Última tentativa", "q.sync_returned":"Modelos retornados pela AA", "q.sync_matched":"Correspondem ao catálogo", "q.sync_unmatched":"Sem correspondência", "q.sync_overrides":"Ajustes manuais", "q.sync_outcome_ok":"sucesso", "q.sync_outcome_failed":"falhou", "q.sync_need_key":"Adicione uma chave na aba Artificial Analysis para sincronizar as pontuações. Ajustes manuais funcionam sem chave.", "q.sync_never":"Nenhuma sincronização foi feita com esta chave. Use Atualizar da AA.", "q.sync_no_models":"A última sincronização não retornou modelos.", "q.status_line":"{matched} modelos com dados de benchmark · {overrides} ajustes manuais", "q.src.live":"ao vivo", "q.src.stale_cache":"em cache (AA inacessível)", "q.src.stale_db":"em cache (snapshot salvo)", "q.src.error":"falha na sincronização", "q.src.missing_key":"sem chave de API", "q.auto_status":"Status do roteamento automático", "q.auto_status_hint":"O que model=\"auto\" escolheria agora. Depende dos provedores configurados, não da sincronização de benchmarks.", "q.auto_no_provider":"Nenhum modelo implantável atende aos requisitos atuais. Adicione uma chave na página Provedores. Isso é independente da sincronização com a Artificial Analysis.", "qa.credential":"Chave de API", "qa.cred_stored":"Armazenada neste servidor (criptografada)", "qa.cred_env":"Do ambiente do servidor", "qa.last_test":"Último teste de conexão", "qa.last_test_ok":"Último teste bem-sucedido", "qa.not_tested":"Ainda não testada", "qa.sync_status":"Sincronização", "qa.tier":"plano {tier}", "qa.troubleshooting":"Solução de problemas de conexão", "qa.status.key_configured":"Chave configurada", "qa.sync.not_configured":"Não configurado", "qa.sync.never_synced":"Nunca sincronizado", "qa.sync.synced":"Sincronizado", "qa.sync.sync_failed":"Falha na sincronização", "qa.err.invalid_key":"Chave inválida", "qa.err.insufficient_tier":"O plano não inclui o endpoint", "qa.err.endpoint_retired":"Endpoint desativado", "qa.err.rate_limited":"Limite de requisições", "qa.err.timeout":"Tempo esgotado", "qa.err.malformed_response":"Resposta inesperada", "qa.err.no_data":"Nenhum modelo retornado", "qa.err.no_catalog_match":"Sem correspondências no catálogo", "qa.err.server_error":"Erro no servidor da AA", "qa.err.connection_failed":"Falha na conexão", "auth.tagline":"Um gateway. Todos os modelos de IA.", "auth.welcome":"Bem-vindo de volta", "auth.subtitle":"Entre no console de administrador desta instalação do GeekCubo.", "auth.api_key":"Chave API", "auth.continue":"Continuar", "nav.search":"Pesquisar", "nav.overview":"Visão geral", "nav.providers":"Provedores", "nav.routing":"Roteação", "nav.analytics":"Análises", "nav.api_keys":"Chaves API", "nav.help_docs":"Ajuda e docs", "nav.sign_out":"Sair", "status.connected":"Conectado", "status.disconnected":"Desconectado", "auth.checking":"Verificando…", "auth.welcome_aboard":"Boas-vindas.", "auth.key_invalid":"Essa chave não funcionou. Verifique o prefixo sk-geek-…", "tab.overview.title":"Visão geral", "tab.overview.sub":"Seu roteador LLM single-tenant em um relance.", "tab.providers.title":"Chaves de provedor", "tab.providers.sub":"BYOK — criptografadas em repouso, usadas para chamar LLMs upstream.", "tab.routing.title":"Roteamento", "tab.routing.sub":"Como model='auto' escolhe o modelo certo para cada solicitação.", "tab.analytics.title":"Análises", "tab.analytics.sub":"Gasto, latência e histórico de solicitações apenas locais.", "tab.keys.title":"Chaves API", "tab.keys.sub":"Chaves sk-geek-* que autenticam tráfego de inferência de SDK e CLI.", "nav.quality":"Qualidade", "tab.quality.title":"Pontuações de qualidade", "tab.quality.sub":"Pontuações reais de benchmark para a estratégia de roteamento por qualidade. Obtidas do Artificial Analysis.", "auth.username":"Usuário", "auth.password":"Senha", "auth.sign_in":"Entrar", "nav.security":"Segurança", "tab.security.title":"Segurança", "tab.security.sub":"Conta de administrador, senha e sessões.", "tab.profiles.title":"Perfis de roteamento", "tab.profiles.sub":"Configurações Auto nomeadas que os clientes escolhem pelo id do modelo.", "tab.integrations.title":"Conectar uma ferramenta", "tab.integrations.sub":"Configuração pronta para OpenCode, Claude Code, Cursor e outros.", "tab.intelligence.title":"Dados de modelos", "tab.intelligence.sub":"De onde vêm os preços e os limites dos modelos.", "auth.loading":"Carregando…", "auth.checking_status":"Verificando o status do administrador.", "auth.signin_title":"Entrar", "auth.signin_sub":"Acesso de administrador a esta instalação do GeekCubo.", "auth.forgot":"Esqueceu sua senha?", "auth.reset_hint":"Redefina-a no host ou no contêiner:", "auth.reset_note":"Chaves, provedores e uso não são afetados.", "auth.setup_title":"Criar conta de administrador", "auth.setup_sub":"Controla esta instalação do GeekCubo: credenciais de provedores, chaves API e roteamento.", "auth.min_password":"Mínimo de 8 caracteres", "auth.confirm_password":"Confirmar senha", "auth.setup_token":"Token de configuração", "auth.from_log":"Do log do servidor", "auth.create_admin":"Criar administrador", "auth.where_token":"Onde está o token de configuração?", "auth.token_hint":"Impresso no log do servidor na primeira inicialização. Para emitir um novo:", "auth.toggle_password":"Mostrar ou ocultar a senha", "ov.spend":"Gasto (7 d)", "ov.savings":"Economia de roteamento", "ov.p50":"latência p50", "ov.models":"Modelos implantáveis", "ov.quickstart":"Início rápido", "ov.recent":"Atividade recente", "prov.title":"Chaves de provedor", "prov.tab_std":"Provedores padrão", "prov.tab_custom":"Provedores personalizados", "routing.strategy":"Estratégia de roteamento", "routing.pools":"Grupos de modelos", "routing.advanced":"Fallback, escalonamento e continuidade", "routing.explain":"Testar uma decisão de roteamento", "profiles.title":"Perfis de roteamento", "int.title":"Conecte sua ferramenta de IA", "md.title":"Fontes de dados de modelos", "md.lookup":"Consulta de preços", "an.spend":"Gasto por modelo", "an.latency":"Latência por provedor", "an.recent":"Solicitações recentes", "keys.title":"Chaves API do roteador", "sec.sessions":"Sessões", "q.setup":"Configurar pontuação de qualidade", "q.models":"Modelos", "preset.heading":"Começar com um modelo", "preset.sub":"Os modelos abrem o editor já preenchido — ajuste tudo antes de salvar.", "preset.economy":"O modelo capaz mais barato para cada solicitação. Menor gasto, sem piso de qualidade.", "preset.premium":"Modelos mais fortes primeiro, ignorando o preço. Para trabalho em que a qualidade manda.", "preset.coding":"Chamadas de ferramenta e prompts longos vão para o pool Hard. Para agentes e editores.", "preset.fast":"Roteamento equilibrado que prefere menor latência no pool.", "ui.profiles":"Perfis", "ui.security":"Segurança", "ui.api_keys":"Chaves API", "ui.connect_a_tool":"Conectar uma ferramenta", "ui.model_data":"Dados de modelos", "ui.connecting":"Conectando…", "ui.language":"Idioma", "ui.light":"Claro", "ui.system":"Sistema", "ui.dark":"Escuro", "ui.openai_compatible_base_url":"URL base compatível com OpenAI", "ui.copy":"Copiar", "ui.use_this_in_any_openai_compatible_client":"Use em qualquer cliente compatível com OpenAI.", "ui.signed_in":"Sessão iniciada", "ui.security_and_sessions":"Segurança e sessões", "ui.api_keys_2":"Chaves API", "ui.sign_out":"Sair", "ui.you_re_up_point_any_openai_sdk_at_your_b":"Tudo pronto: aponte qualquer SDK da OpenAI para sua URL base.", "ui.last_5_requests_routed_through_this_serv":"Últimas 5 requisições roteadas por este servidor.", "ui.view_all":"Ver todas", "ui.no_requests_yet":"Ainda não há requisições.", "ui.new_here_get_fully_set_up_in_2_minutes":"Primeira vez? Configure tudo em 2 minutos", "ui.re_enter_as_a_named_provider":"Reinserir como provedor nomeado", "ui.remove_legacy_entry":"Remover entrada legada", "ui.provider":"Provedor", "ui.others_openai_format":"Outros (formato OpenAI)", "ui.api_key":"Chave API", "ui.provider_name":"Nome do provedor", "ui.display_name_a_unique_internal_slug_is_d":"Nome de exibição. Um slug interno único é derivado automaticamente.", "ui.api_base_url":"URL base da API", "ui.usually_ends_in_v1_must_be_https_unless_":"Geralmente termina em /v1. Deve ser https, a menos que o host esteja em CUSTOM_PROVIDER_ALLOWED_LOCAL_HOSTS.", "ui.api_key_2":"Chave API", "ui.encrypted_at_rest_never_displayed_again_":"Criptografada em repouso. Nunca é exibida novamente após salvar.", "ui.prefix":"Prefixo", "ui.status":"Status", "ui.no_provider_keys_yet":"Ainda não há chaves de provedor", "ui.add_at_least_one_to_start_routing_real_t":"Adicione pelo menos uma para começar a rotear tráfego real. Escolha um provedor acima ou clique em uma sugestão rápida.", "ui.lowest_cost_that_clears_your_quality_flo":"O menor custo que passa do seu piso de qualidade. Opção segura com qualquer número de provedores.", "ui.recommended":"Recomendado", "ui.lowest_per_token_cost_meeting_the_reques":"O menor custo por token que atende às capacidades da requisição. A qualidade da saída pode variar.", "ui.highest_score_from_artificial_analysis_o":"A maior pontuação do Artificial Analysis ou das suas substituições manuais. Sem pontuações, usa o preço como aproximação.", "ui.re_ranks_by_observed_success_rate_and_la":"Reordena por taxa de sucesso e latência observadas quando cada modelo acumula 20+ requisições aqui. Até então: Equilibrado.", "ui.sends_each_request_to_your_mundane_or_ha":"Envia cada requisição ao seu pool Mundane ou Hard com base em sinais observáveis (ferramentas, tamanho, comprimento).", "ui.highest_throughput_and_lowest_first_toke":"A maior taxa de transferência e a menor latência do primeiro token segundo dados de referência. Mantido por compatibilidade.", "ui.legacy":"Legado", "ui.registered_models":"Modelos registrados", "ui.show":"Mostrar", "ui.deployable":"Implantáveis", "ui.custom_providers":"Provedores personalizados", "ui.model":"Modelo", "ui.capabilities":"Capacidades", "ui.context":"Contexto", "ui.price_1m_in_out":"Preço /1M (ent · saí)", "ui.availability":"Disponibilidade", "ui.pools":"Pools", "ui.previous":"Anterior", "ui.next":"Próximo", "ui.fallback_and_escalation_always_keep_the_":"Fallback e escalonamento sempre preservam as capacidades exigidas pela requisição. As decisões ocorrem antes do início; os modelos nunca mudam no meio do stream.", "ui.maximum_attempts_primary_fallbacks":"Tentativas máximas (principal + fallbacks)", "ui.what_counts_as_retryable":"O que conta como repetível", "ui.quality_floor_percentile_0_off":"Piso de qualidade (percentil, 0 = desligado)", "ui.needs_quality_scores_ignored_and_reporte":"Precisa de pontuações de qualidade; é ignorado (e informado) quando não há nenhuma.", "ui.what_the_quality_floor_does":"O que o piso de qualidade faz", "ui.balanced_weighs_price_against_quality_th":"Equilibrado pesa preço e qualidade. O piso exclui modelos abaixo desse percentil, então um modelo muito barato e fraco não pode vencer. Defina 0 para desligar totalmente.", "ui.messages":"Mensagens ≥", "ui.prompt_characters":"Caracteres do prompt ≥", "ui.how_request_signals_are_measured":"Como os sinais da requisição são medidos", "ui.mode":"Modo", "ui.off":"Desligado", "ui.manual_client_sends_x_geek_escalate":"Manual (o cliente envia x-geek-escalate)", "ui.auto_after_repeated_upstream_failures":"Automático (após falhas repetidas do provedor)", "ui.failures_before_escalating":"Falhas antes de escalar", "ui.max_escalations_per_conversation":"Máximo de escalonamentos por conversa", "ui.destination_pool":"Pool de destino", "ui.when_escalation_triggers":"Quando o escalonamento dispara", "ui.remember_for_minutes":"Lembrar por (minutos)", "ui.what_continuity_does":"O que a continuidade faz", "ui.save_routing_policy":"Salvar política de roteamento", "ui.dry_run_shows_which_model_auto_would_cho":"Simulação: mostra qual modelo o Auto escolheria e por quê. Nada é enviado ao provedor.", "ui.messages_2":"Mensagens", "ui.prompt_chars":"Caracteres do prompt", "ui.explain":"Explicar", "ui.three_filters_applied_in_order":"Três filtros, aplicados em ordem.", "ui.how_each_strategy_maps_to_litellm_router":"Como cada estratégia mapeia para o LiteLLM Router", "ui.strategy":"Estratégia", "ui.import_json":"Importar JSON", "ui.new_profile":"Novo perfil", "ui.generates_configuration_that_points_a_cl":"Gera configuração que aponta um cliente para este GeekCubo. As chaves são referenciadas por variável de ambiente, nunca embutidas.", "ui.search_tools":"Buscar ferramentas", "ui.routing_profile_or_model":"Perfil de roteamento ou modelo", "ui.endpoint":"Endpoint", "ui.format":"Formato", "ui.download":"Baixar", "ui.add_source":"Adicionar fonte", "ui.name":"Nome", "ui.https_url_models_dev_compatible_json":"URL HTTPS (JSON compatível com models.dev)", "ui.save_source":"Salvar fonte", "ui.cancel":"Cancelar", "ui.shows_what_each_enabled_source_reports_f":"Mostra o que cada fonte ativa reporta para um modelo e qual valor o GeekCubo usaria. Seus preços configurados sempre vencem.", "ui.look_up":"Consultar", "ui.routing":"Roteamento", "ui.volume":"Volume", "ui.routing_decisions":"Decisões de roteamento", "ui.how_auto_requests_were_classified_and_wh":"Como as requisições Auto foram classificadas e para onde foram.", "ui.by_tier":"Por tier", "ui.by_strategy":"Por estratégia", "ui.by_routing_id":"Por id de roteamento", "ui.top_models_served":"Modelos mais servidos", "ui.reliability":"Confiabilidade", "ui.errors_by_cause":"Erros por causa", "ui.compare_against_a_baseline_model":"Comparar com um modelo de referência", "ui.none":"Nenhum", "ui.compare":"Comparar", "ui.how_the_comparison_is_calculated":"Como a comparação é calculada", "ui.p50_and_p99_sourced_from_local_request_l":"p50 e p99 — provenientes dos logs locais de requisições.", "ui.requests":"Requisições", "ui.newest_first_click_a_row_to_copy_its_tra":"Mais recentes primeiro. Clique em uma linha para copiar seu trace ID.", "ui.when":"Quando", "ui.tokens_in_out":"Tokens (ent / saí)", "ui.latency":"Latência", "ui.no_traffic_yet":"Ainda sem tráfego", "ui.once_you_start_sending_requests_they_ll_":"Quando você começar a enviar requisições, elas aparecerão aqui em tempo real.", "ui.expires":"Expira", "ui.never":"Nunca", "ui.7_days":"7 dias", "ui.30_days":"30 dias", "ui.90_days":"90 dias", "ui.1_year":"1 ano", "ui.use_it_with_opencode":"Use com o OpenCode:", "ui.created":"Criada", "ui.last_used":"Último uso", "ui.actions":"Ações", "ui.no_api_keys":"Nenhuma chave API", "ui.generate_one_above_to_start_sending_requ":"Gere uma acima para começar a enviar requisições de um SDK ou da CLI.", "ui.administrator":"Administrador", "ui.the_single_local_account_that_controls_t":"A única conta local que controla esta instalação.", "ui.password_was_reset_from_the_command_line":"A senha foi redefinida pela linha de comando", "ui.change_password":"Alterar senha", "ui.current_password":"Senha atual", "ui.new_password":"Nova senha", "ui.confirm_new_password":"Confirmar nova senha", "ui.update_password":"Atualizar senha", "ui.signed_in_browsers_for_this_administrato":"Navegadores com sessão iniciada para este administrador. As sessões expiram após 12 horas, ou 60 minutos ociosos.", "ui.log_out_all_other_sessions":"Sair de todas as outras sessões", "ui.device":"Dispositivo", "ui.last_active":"Última atividade", "ui.local_recovery":"Recuperação local", "ui.password_recovery_is_local_only_by_desig":"A recuperação de senha é apenas local por design — não há redefinição por e-mail nem endpoint público que a altere.", "ui.open_a_shell_where_geekcubo_runs_host_or":"Abra um shell onde o GeekCubo roda (host ou contêiner).", "ui.choose_a_new_password_at_the_prompt_all_":"Escolha uma nova senha no prompt. Todas as sessões do painel são encerradas; chaves API, provedores e dados de uso não são afetados.", "ui.artificial_analysis_api_key":"Chave API do Artificial Analysis", "ui.optional":"(opcional)", "ui.save_key":"Salvar chave", "ui.remove_stored_key":"Remover chave armazenada", "ui.how_quality_scoring_works":"Como a pontuação de qualidade funciona", "ui.paste_it_above_and_save_it_is_encrypted_":"Cole acima e salve. É criptografada em repouso e o que já estava em cache é descartado para que a próxima atualização use a nova chave.", "ui.quality_scores":"Pontuações de qualidade", "ui.where_these_numbers_come_from":"De onde vêm estes números", "ui.manual":"Manual", "ui.effective":"Efetiva", "ui.m_blended":"$/M combinado", "ui.help_and_docs":"Ajuda e documentação", "ui.what_is_geekcubo":"O que é GeekCubo?", "ui.60_second_quickstart":"Início rápido em 60 segundos", "ui.keyboard_shortcuts":"Atalhos de teclado", "ui.switch_tabs":"Trocar de aba", "ui.command_palette":"Paleta de comandos", "ui.toggle_this_help":"Mostrar ou ocultar esta ajuda", "ui.close_drawers_palette":"Fechar painéis / paleta", "ui.going_further":"Indo além", "js.ov_empty_a":"Ainda não há requisições.", "js.ov_empty_b":"Quando você enviar sua primeira chamada, ela aparecerá aqui.", "js.ra_unavailable":"Análises de roteamento indisponíveis.", "js.no_spend":"Ainda não há gasto registrado neste período.", "js.no_traffic":"Ainda sem tráfego", "toast.copied":"Copiado para a área de transferência", "toast.copy_blocked":"Não foi possível copiar — o navegador bloqueou", "toast.signed_in":"Sessão iniciada como {name}", "toast.admin_created":"Administrador {name} criado", "toast.signed_out":"Sessão encerrada", "toast.load_providers_failed":"Não foi possível carregar os provedores: {msg}", "toast.removed_provider":"{name} removido", "toast.api_key_empty":"A chave API não pode ficar vazia", "toast.saved_provider":"Chave de {name} salva", "toast.load_custom_failed":"Não foi possível carregar os provedores personalizados: {msg}", "toast.updated":"{name} atualizado", "toast.model_id_empty":"O ID do modelo não pode ficar vazio", "toast.model_id_dup":"Esse ID de modelo já está registrado", "toast.model_saved":"Modelo salvo", "toast.select_one_model":"Selecione ao menos um novo modelo", "toast.added_models_one":"1 modelo adicionado", "toast.added_models_many":"{count} modelos adicionados", "toast.load_routing_failed":"Não foi possível carregar o roteamento: {msg}", "toast.routing_strategy":"Estratégia de roteamento: {name}", "toast.policy_saved":"Política de roteamento salva", "toast.load_models_failed":"Não foi possível carregar os modelos: {msg}", "toast.load_analytics_failed":"Não foi possível carregar as análises: {msg}", "toast.load_keys_failed":"Não foi possível carregar as chaves: {msg}", "toast.revoked":"{name} revogada", "toast.name_empty":"O nome não pode ficar vazio", "toast.key_renamed":"Chave renomeada", "toast.name_first":"Dê um nome à chave primeiro", "toast.created":"{name} criada", "toast.load_security_failed":"Não foi possível carregar a segurança: {msg}", "toast.password_updated":"Senha atualizada — outros dispositivos foram desconectados", "toast.load_quality_failed":"Não foi possível carregar as pontuações: {msg}", "toast.score_range":"A pontuação deve ser um número entre 0 e 100", "toast.override_set":"Substituição definida para {name}", "toast.reset":"{name} redefinido", "toast.aa_saved":"Chave Artificial Analysis salva", "toast.stored_removed":"Chave armazenada removida", "toast.remove_key_failed":"Não foi possível remover a chave: {msg}", "toast.aa_refreshed":"Pontuações do Artificial Analysis atualizadas", "toast.refresh_failed":"Falha ao atualizar: {msg}", "toast.load_profiles_failed":"Não foi possível carregar os perfis: {msg}", "toast.duplicated":"{name} duplicado", "toast.now_default":"{name} agora é o padrão", "toast.deleted":"{name} excluído", "toast.default_reassigned":" — o padrão agora é auto", "toast.saved_profile":"{name} salvo", "toast.file_too_large":"Esse arquivo é grande demais para ser uma exportação de perfil.", "toast.load_integrations_failed":"Não foi possível carregar as integrações: {msg}", "toast.load_mi_failed":"Não foi possível carregar as fontes de dados: {msg}", "toast.source_added":"Fonte adicionada", "toast.legacy_removed":"Entrada legada \"__custom__\" removida", "toast.saved_as":"Salvo {name} como {slug}. Busque os modelos abaixo.", "confirm.remove_provider":"Remover a chave de {name}? As requisições roteadas para {name} começarão a falhar.", "confirm.remove_model":"Remover o modelo {name}?", "confirm.remove_custom":"Remover o provedor \"{name}\" e seus modelos?", "confirm.sign_out_others":"Encerrar a sessão em todos os outros navegadores deste administrador?", "confirm.reset_score":"Redefinir {name} para a pontuação AA?", "confirm.remove_aa_key":"Remover a chave Artificial Analysis armazenada? Uma chave de ambiente assume novamente, se houver.", "confirm.change_slug":"Alterar o identificador de API de \"{old}\" para \"{new}\"?\n\nTodo cliente que enviar model: \"{old}\" deixará de funcionar.", "confirm.delete_source":"Excluir esta fonte de metadados?", "confirm.legacy_remove":"Remover permanentemente a chave de provedor legada \"__custom__\" ({prefix})?\n\nEla não é usada para roteamento. Guarde a chave em outro lugar se ainda precisar — não pode ser recuperada.", "confirm.revoke":"Revogar \"{name}\"?\n\nClientes que usam esta chave recebem 401 imediatamente. Irreversível — emita uma nova chave se precisar de acesso novamente.", "confirm.rotate":"Rotacionar \"{name}\"?\n\nUma chave substituta com as mesmas restrições é criada e exibida uma vez.\n\nOK = revogar a chave antiga agora (troca imediata).\nCancelar = manter a chave antiga até você revogá-la.", "prompt.rename_key":"Renomear a chave \"{name}\" para:", "prompt.set_score":"Definir pontuação de qualidade manual para {name} (0-100):", "prompt.aa_current":"A pontuação AA atual é: {score}", "prompt.override_note":"Nota opcional (por que substituir?):", "auth.session_expired":"Sua sessão expirou. Entre novamente.", "auth.enter_creds":"Digite seu usuário e senha.", "auth.creds_required":"Usuário e senha são obrigatórios.", "auth.pw_mismatch":"As senhas não coincidem.", "auth.paste_token":"Cole o token de configuração de uso único do log do servidor.", "auth.signed_out":"Sessão encerrada.", "auth.pw_match":"As senhas coincidem.", "auth.pw_mismatch_yet":"As senhas ainda não coincidem.", "auth.new_pw_mismatch":"As novas senhas não coincidem.", "auth.fill_three":"Preencha os três campos.", "qa.connection":"Conexão com Artificial Analysis", "qa.test":"Testar conexão", "qa.replace":"Substituir chave", "qa.add":"Adicionar chave", "qa.remove":"Remover chave", "qa.last_sync":"Última sincronização bem-sucedida", "qa.last_error":"Último erro", "qa.never":"ainda não sincronizado", "qa.from_env":"do ambiente", "qa.saving":"Salvando…", "qa.key_hint":"Criptografada neste servidor e nunca exibida novamente. A chave anterior permanece ativa até salvar esta.", "qa.daily_limit_label":"Limite diário da sua chave", "qa.daily_limit_hint":"Requisições por 24 horas, conforme sua página de conta da Artificial Analysis. Deixe em branco para o limite documentado de 100/dia.", "qa.status.not_configured":"Não configurada", "qa.status.connected":"Conectada", "qa.status.invalid_key":"Chave inválida", "qa.status.rate_limited":"Limite atingido", "qa.status.connection_failed":"Falha de conexão", "qa.status.cached":"Dados em cache", "pricing.legend":"Preços", "pricing.allow_estimates":"Permitir estimativas de referência no Auto, Mais barato e limites de custo", "pricing.allow_estimates_help":"Desativado por padrão. Apenas preços confirmados do provedor são comparados; modelos com apenas uma estimativa de referência ficam fora do Auto. Quando ativado, cada decisão baseada em estimativa é sinalizada.", "confirm.bulk_remove_models":"Remover {count} modelo(s) selecionado(s)? Solicitações fixadas para eles falharão.", "nav.chat":"Conversas", "tab.chat.title":"Conversas", "tab.chat.sub":"Fale com seus modelos implantados. Roteado, em cache e medido como o tráfego de SDK.", "ui.open_chat":"Abrir o chat", "ui.open_chat_hint":"Converse com seus modelos implantados pelo navegador — mesmo roteamento, cache e rastreio de custo que o tráfego de SDK.", "chat.new":"Novo chat", "chat.settings_title":"Configurações do chat", "chat.default_title":"Novo chat", "chat.clear_history":"Limpar histórico…", "chat.conversations_aria":"Conversas", "chat.model_aria":"Modelo", "chat.regenerate":"Regenerar resposta", "chat.empty_title":"Pergunte qualquer coisa.", "chat.empty_sub":"As solicitações passam pelo motor — mesmo roteamento, cache e rastreio de custo que o tráfego de SDK.", "chat.input_placeholder":"Mensagem para GeekCubo…", "chat.send":"Enviar", "chat.stop":"Parar", "chat.system_prompt":"Prompt do sistema…", "chat.system_prompt_set":"Prompt do sistema ✓", "chat.system_ph":"Você é um assistente prestativo…", "chat.system_help":"Vazio = usar o padrão do chat. Salvo por conversa.", "chat.save_prompt":"Salvar prompt", "chat.default_model":"Modelo padrão", "chat.default_model_help":"Usado em novas conversas. O seletor da própria conversa o substitui.", "chat.temperature":"Temperatura", "chat.max_tokens":"Máx. tokens de saída", "chat.default_system_prompt":"Prompt de sistema padrão", "chat.default_system_prompt_ph":"Você é um assistente de engenharia conciso.", "chat.default_system_help":"Aplica-se a conversas sem prompt próprio.", "chat.save_history":"Salvar o histórico de chat neste servidor", "chat.retention_days":"Manter conversas por (dias)", "chat.retention_help":"Conversas mais antigas são removidas. Vazio mantém tudo.", "chat.font_size":"Tamanho do texto", "chat.fs_small":"Pequeno", "chat.fs_medium":"Médio", "chat.fs_large":"Grande", "chat.enter_to_send":"Enter envia a mensagem", "chat.privacy_note":"As conversas ficam no banco de dados deste servidor. As solicitações vão para os provedores que você configurou, exatamente como o tráfego de SDK.", "chat.privacy_ack":"Entendo que o tráfego de chat vai para os provedores configurados", "chat.save_settings":"Salvar configurações", "chat.model_auto":"Auto (o roteador escolhe)", "chat.no_conversations":"Ainda não há conversas.", "chat.delete_convo_title":"Excluir esta conversa", "chat.kbd_enter_send":"Enter para enviar · Shift+Enter para nova linha", "chat.kbd_ctrl_enter_send":"Ctrl+Enter para enviar · Enter para nova linha", "chat.tokens_meta":"{in} entrada · {out} saída", "chat.error_note":"A geração parou antes de terminar.", "chat.upstream_error":"O modelo upstream retornou um erro.", "toast.chat_load_failed":"Não foi possível carregar os dados do chat: {msg}", "toast.chat_failed":"Falha na solicitação de chat: {msg}", "toast.chat_convo_deleted":"Conversa excluída", "toast.chat_cleared":"{count} conversas limpas", "toast.chat_temp_range":"A temperatura deve estar entre 0 e 2", "toast.chat_settings_saved":"Configurações do chat salvas", "toast.chat_open_convo":"Abra uma conversa primeiro", "toast.chat_saved_prompt":"Prompt de sistema salvo para esta conversa", "confirm.delete_conversation":"Excluir esta conversa?\n\nAs mensagens são removidas do banco de dados do servidor. Os registros de uso e custo permanecem nas análises.", "confirm.clear_chat_history":"Excluir TODAS as conversas salvas?\n\nTodas as mensagens de chat armazenadas neste servidor são removidas. Os registros de uso e custo permanecem nas análises.", "q.ov_score":"Pontuação manual (0–100)", "q.ov_note":"Nota", "q.ov_model_ph":"ex.: openai/gpt-4o, anthropic/claude-…", "q.ov_note_ph":"Por que substitui a pontuação da AA", "q.ov_apply":"Aplicar substituição", "q.ov_clear":"Remover substituição", "q.ov_help":"Um ou mais ids de modelo, separados por vírgulas — a substituição se aplica a todos os modelos listados. Pontuações manuais sempre vencem as da AA.", "toast.q_ids_required":"Insira pelo menos um id de modelo", "toast.q_too_many":"O lote é limitado a 500 ids de modelo", "toast.q_bulk_set":"Substituição definida para {count} modelo(s)", "toast.q_bulk_clear":"Substituições removidas de {count} modelo(s)", "providers.bulk_actions":"Ações em massa de modelos", "providers.select_all":"Selecionar tudo", "providers.selected_count":"{count} selecionados", "providers.bulk_capability":"Capacidade", "providers.bulk_capability_state":"Estado da capacidade", "providers.cap_tools":"Ferramentas", "providers.cap_vision":"Visão", "providers.cap_supported":"Suportado", "providers.cap_unsupported":"Não suportado", "providers.cap_unknown":"Desconhecido", "providers.cap_catalog":"Usar catálogo", "providers.cap_json_mode":"Modo JSON", "providers.cap_json_schema":"Esquema JSON", "providers.apply":"Aplicar", "providers.enable":"Ativar", "providers.disable":"Desativar", "providers.remove_selected":"Remover selecionados", "providers.resolve_metadata":"Resolver", "toast.metadata_resolved":"Metadados: {resolved} resolvidos, {ambiguous} ambíguos, {unmatched} sem correspondência, {failed} falhas.", "select.search_ph":"Pesquisar chaves do catálogo…", "providers.catalog_key_ph":"Pesquisar chaves do catálogo…", "select.remove_item":"Remover {name}", "select.use_custom":"Usar \"{name}\"", "select.no_matches":"Nenhum modelo correspondente", "select.more_results":"Mais {count} — continue digitando para filtrar", "q.ov_model_search_ph":"Pesquise e escolha modelos…", "q.ov_help_picker":"Pesquise e escolha um ou mais modelos, ou marque linhas na tabela abaixo. Pontuações manuais sempre prevalecem sobre as do AA.", "q.filter_ph":"Filtrar modelos…", "q.select_filtered":"Selecionar filtrados", "q.select_all_filtered":"Selecionar todos os modelos filtrados", "q.deselect_all":"Desmarcar tudo", "q.bulk_set":"Definir pontuação dos selecionados", "q.bulk_clear":"Limpar substituições selecionadas", "q.select_model":"Selecionar {name}", "confirm.q_bulk_clear":"Limpar substituições manuais de {count} modelos selecionados?", "qa.daily_limit_short":"Limite diário", "chat.attach":"Anexar arquivos", "chat.attach_drop":"Solte arquivos para anexar", "chat.attach_remove":"Remover anexo", "chat.attach_unreadable":"Não foi possível ler este arquivo; apenas o nome é enviado.", "chat.attach_uploading":"Enviando…", "chat.attach_too_large":"Muito grande (máx. {max} MB)", "toast.chat_attach_failed":"Não foi possível anexar {name}: {msg}", "toast.chat_attach_disabled":"Os anexos estão desativados neste servidor.", "toast.chat_attach_too_many":"No máximo {max} anexos por mensagem.", "toast.chat_attach_extract_failed":"{name}: não foi possível ler ({msg})", "toast.chat_attach_wait":"Aguarde o envio terminar.", "chat.search_toggle":"Pesquisa na web", "chat.search_settings":"Pesquisa na web", "chat.search_help":"Quando ativada, o GeekCubo pesquisa na web antes de responder e cita as páginas usadas. Os resultados são injetados como mensagem de sistema, por isso qualquer modelo pode usá-los.", "chat.search_mode":"Modo de pesquisa", "chat.search_mode_off":"Desligada", "chat.search_mode_manual":"Manual (por mensagem)", "chat.search_mode_auto":"Automática (reservada)", "chat.search_mode_help":"O modo manual mostra um botão no compositor. O automático está reservado e ainda não foi implementado.", "chat.search_backend":"Serviço de pesquisa", "chat.search_backend_none":"Escolha um serviço…", "chat.search_backend_searxng":"SearXNG (auto-hospedado)", "chat.search_backend_brave":"API do Brave Search", "chat.search_backend_tavily":"Tavily", "chat.search_url":"URL do SearXNG", "chat.search_url_ph":"http://searxng:8080/", "chat.search_url_help":"URL base da sua instância do SearXNG. O perfil search do instalador disponibiliza-a na rede interna.", "chat.search_api_key":"Chave de API", "chat.search_api_key_ph":"Cole uma chave nova para substituir a guardada", "chat.search_key_clear":"Remover chave guardada", "chat.search_key_help":"Guardada cifrada neste servidor e nunca mais exibida. Brave e Tavily exigem chave; o SearXNG não.", "chat.search_max_searches":"Máximo de pesquisas por conversa", "chat.search_max_results":"Resultados por pesquisa", "chat.search_max_fetches":"Páginas a obter por pesquisa", "chat.search_timeout":"Tempo limite da pesquisa (segundos)", "chat.search_test":"Testar ligação", "chat.search_testing":"A testar…", "chat.search_test_ok":"{count} resultados em {ms} ms", "chat.search_test_failed":"O teste de pesquisa falhou: {msg}", "chat.search_key_state_unset":"Nenhuma chave guardada", "chat.search_key_state_set":"Chave guardada", "chat.search_key_state_undecryptable":"Não é possível decifrar a chave guardada", "chat.context_budget":"Contexto: {tokens} / {budget} tokens", "chat.context_omitted":"{count} mensagens anteriores omitidas", "chat.sources":"Fontes", "chat.search_used":"pesquisa na web: {backend}", "toast.search_saved":"Definições de pesquisa na web guardadas", "toast.search_save_failed":"Não foi possível guardar as definições de pesquisa: {msg}", "toast.search_test_failed":"O teste de pesquisa na web falhou", "nav.local":"IA local", "tab.local.title":"IA local", "tab.local.sub":"Sirva modelos das suas próprias máquinas através deste roteador.", "local.title":"Conexão de IA local", "local.sub":"Encaminhe para modelos executados nas suas próprias máquinas. Um pequeno conector disca para este servidor, então nenhuma porta é aberta e nenhum túnel de entrada é necessário.", "local.refresh":"Atualizar", "local.setup_button":"Configurar uma máquina", "local.feature_off_title":"A conexão de IA local está desativada no servidor", "local.feature_off_body":"Defina LOCAL_CONNECT_ENABLED=true no ambiente do servidor e reinicie; depois recarregue esta página.", "local.url_missing_title":"Nenhuma URL pública configurada", "local.url_missing_body":"Defina LOCAL_CONNECT_PUBLIC_URL com o endereço para o qual os conectores devem discar (por exemplo https://example.com) para que o comando de instalação e os arquivos de serviço sejam preenchidos.", "local.settings_title":"Comportamento do roteamento", "local.settings_sub":"Controla se os modelos locais participam do Auto e se uma requisição pode recorrer à nuvem.", "local.set_enabled":"Habilitar máquinas locais para roteamento", "local.set_auto":"Incluir modelos locais na seleção automática", "local.set_no_fallback":"Nunca recorrer à nuvem quando um modelo local falhar", "local.settings_help":"Modelos locais só são considerados para o Auto quando têm preço zero confirmado e a máquina está aprovada e conectada. Com \"nunca recorrer\" ativado, uma requisição apenas local falha em vez de ser atendida por um provedor na nuvem.", "local.save_settings":"Salvar", "local.settings_saved":"Configurações de roteamento local salvas.", "local.machines_title":"Máquinas", "local.machines_sub":"Cada máquina é um conector. Máquinas pendentes ficam visíveis mas não recebem tráfego até serem aprovadas.", "local.machines_empty":"Ainda não há máquinas. Use \"Configurar uma máquina\" para gerar um código de registro.", "local.enrollments_title":"Códigos de registro", "local.enrollments_sub":"Códigos de uso único que permitem registrar um conector. Cada código é consumido na primeira conexão de uma máquina.", "local.new_code":"Novo código", "local.install_title":"Instalar o conector", "local.install_sub":"Execute isto na máquina que hospeda seus modelos (Ollama, LM Studio, vLLM, llama.cpp ou qualquer servidor compatível com [OI]).", "local.service_files":"Executar como serviço", "local.delete":"Excluir", "local.never":"nunca", "local.ctx_suffix":"contexto", "local.ctx_unknown":"contexto desconhecido", "local.no_models":"Esta máquina ainda não reportou nenhum modelo.", "local.no_enrollments":"Nenhum código de registro.", "local.enroll_active":"Ativo", "local.enroll_used":"Usado", "local.status_online":"Conectada", "local.status_offline":"Desconectada", "local.status_pending":"Aguardando aprovação", "local.status_approved":"Aprovada", "local.status_revoked":"Revogada", "local.pending_note":"Esta máquina aguarda aprovação. Os modelos estão listados mas não receberão tráfego.", "local.action_approve":"Aprovar", "local.action_discover":"Descobrir modelos", "local.action_revoke":"Revogar", "local.action_rotate":"Rotacionar credencial", "local.action_delete":"Excluir", "local.meta_host":"Nome do host", "local.meta_platform":"Plataforma", "local.meta_agent":"Versão do conector", "local.meta_adapters":"Adaptadores", "local.meta_seen":"Visto por último", "local.col_model":"Modelo", "local.col_adapter":"Tipo de adaptador", "local.col_context":"Contexto", "local.col_caps":"Capacidades", "local.col_enabled":"Ativado", "local.kpi_machines":"Máquinas", "local.kpi_online":"Conectadas agora", "local.kpi_pending":"Aguardando aprovação", "local.kpi_models":"Modelos", "local.toast_approved":"Máquina aprovada.", "local.toast_revoked":"Máquina revogada.", "local.toast_deleted":"Máquina excluída.", "local.toast_discovered":"Lista de modelos atualizada.", "local.confirm_revoke":"Revogar esta máquina? O conector dela é desconectado imediatamente e não poderá reconectar até que você rotacione a credencial.", "local.confirm_delete_machine":"Excluir esta máquina e sua lista de modelos? Isto não pode ser desfeito.", "local.confirm_rotate":"Rotacionar a credencial desta máquina? O conector em execução continua funcionando até reconectar, quando a credencial antiga será rejeitada.", "local.confirm_delete_enrollment":"Excluir este código de registro?", "local.credential_once_title":"Copie a nova credencial agora", "local.credential_once_body":"Ela é mostrada apenas uma vez. Guarde-a na configuração do conector na máquina.", "local.wizard_title":"Conectar uma máquina local", "local.wizard_close":"Fechar", "local.wizard_back":"Voltar", "local.wizard_next":"Avançar", "local.wizard_done":"Concluir", "local.step1":"Ativar", "local.step2":"Código de registro", "local.step3":"Instalar", "local.step4":"Registrar", "local.step5":"Iniciar", "local.step6":"Aprovar", "local.step7":"Modelos", "local.step8":"Roteamento automático", "local.w0_title":"Ative o recurso", "local.w0_body":"A conexão de IA local é um recurso do servidor. Ele precisa estar habilitado antes que os conectores possam se registrar.", "local.w0_ready":"O recurso está habilitado. Continue para criar um código de registro.", "local.w0_blocked":"O recurso está desativado neste servidor. Defina LOCAL_CONNECT_ENABLED=true e reinicie; depois recarregue esta página.", "local.w1_title":"Crie um código de registro", "local.w1_body":"Um código de uso único autoriza um único conector a se registrar. Ele expira após um curto período.", "local.w1_name":"Nome da máquina (opcional)", "local.w1_name_ph":"ex.: escritorio-gpu", "local.w1_name_help":"Um rótulo para reconhecer esta máquina na lista. Você pode renomeá-la depois.", "local.w1_created":"Código de registro criado", "local.w2_title":"Instale o pacote do conector", "local.w2_body":"Na máquina que hospeda seus modelos, instale o conector. É necessário Python 3.11 ou mais recente.", "local.w2_note":"Instale em um ambiente virtual para mantê-lo isolado dos pacotes do sistema.", "local.w3_title":"Registre a máquina", "local.w3_body":"Execute o comando de registro com o código do passo 2. A credencial é gravada no arquivo de configuração do conector.", "local.w3_note":"O código é de uso único. Se expirou, crie um novo.", "local.w4_title":"Inicie o conector", "local.w4_body":"Execute o conector em primeiro plano para vê-lo conectar e depois mova-o para um serviço.", "local.w4_note":"O conector mantém um único WebSocket de saída aberto e reconecta automaticamente.", "local.w5_title":"Aguarde a máquina aparecer", "local.w5_body":"Quando o conector conectar, a máquina aparecerá aqui. Atualize se demorar um pouco.", "local.w5_seen":"{name} conectou-se.", "local.w5_waiting":"Nenhuma máquina se conectou ainda.", "local.w5_recheck":"Verificar novamente", "local.w6_title":"Aprove a máquina", "local.w6_body":"Uma máquina nova permanece pendente até que um administrador a aprove. Até lá nada é roteado para ela.", "local.w6_none":"Ainda não há máquina para aprovar.", "local.w6_must_approve":"Aprove a máquina pendente antes de continuar.", "local.w7_title":"Habilite modelos locais no Auto", "local.w7_body":"Ative \"Incluir modelos locais na seleção automática\" e habilite os modelos para os quais deseja rotear. Modelos locais só são escolhidos para o Auto quando o preço é zero confirmado.", "local.w7_done":"A configuração está completa. Os modelos locais agora aparecem nas páginas de Provedores e Roteamento." },
  ru: { "q.tabs_label":"Разделы качества", "q.tab_models":"Модели", "q.tab_scores":"Оценки качества", "q.tab_aa":"Подключение Artificial Analysis", "q.col_availability":"Доступность", "q.avail_yes":"доступна", "q.avail_no":"нет ключа провайдера", "q.avail_no_title":"Ни один настроенный ключ провайдера не обслуживает эту модель. Наличие данных бенчмарка не делает модель развёртываемой.", "q.sync_title":"Синхронизация бенчмарков", "q.sync_last_ok":"Последняя успешная синхронизация", "q.sync_last_attempt":"Последняя попытка", "q.sync_returned":"Моделей получено от AA", "q.sync_matched":"Сопоставлено с каталогом", "q.sync_unmatched":"Без сопоставления", "q.sync_overrides":"Ручные оценки", "q.sync_outcome_ok":"успешно", "q.sync_outcome_failed":"ошибка", "q.sync_need_key":"Добавьте ключ на вкладке Artificial Analysis, чтобы синхронизировать оценки. Ручные оценки работают без ключа.", "q.sync_never":"С этим ключом синхронизация ещё не выполнялась. Нажмите «Обновить из AA».", "q.sync_no_models":"Последняя синхронизация не вернула моделей.", "q.status_line":"Моделей с данными бенчмарка: {matched} · ручных оценок: {overrides}", "q.src.live":"актуально", "q.src.stale_cache":"из кэша (AA недоступен)", "q.src.stale_db":"из кэша (сохранённый снимок)", "q.src.error":"ошибка синхронизации", "q.src.missing_key":"нет API-ключа", "q.auto_status":"Состояние авто-маршрутизации", "q.auto_status_hint":"Что выбрал бы model=\"auto\" прямо сейчас. Зависит от настроенных провайдеров, а не от синхронизации бенчмарков.", "q.auto_no_provider":"Ни одна развёртываемая модель не удовлетворяет текущим требованиям. Добавьте ключ на странице «Провайдеры». Это не связано с синхронизацией Artificial Analysis.", "qa.credential":"API-ключ", "qa.cred_stored":"Хранится на этом сервере (зашифрован)", "qa.cred_env":"Из окружения сервера", "qa.last_test":"Последняя проверка подключения", "qa.last_test_ok":"Последняя успешная проверка", "qa.not_tested":"Ещё не проверялся", "qa.sync_status":"Синхронизация", "qa.tier":"тариф {tier}", "qa.troubleshooting":"Устранение проблем подключения", "qa.status.key_configured":"Ключ задан", "qa.sync.not_configured":"Не настроено", "qa.sync.never_synced":"Ещё не синхронизировано", "qa.sync.synced":"Синхронизировано", "qa.sync.sync_failed":"Ошибка синхронизации", "qa.err.invalid_key":"Недействительный ключ", "qa.err.insufficient_tier":"Тариф не включает этот эндпоинт", "qa.err.endpoint_retired":"Эндпоинт выведен из эксплуатации", "qa.err.rate_limited":"Превышен лимит запросов", "qa.err.timeout":"Превышено время ожидания", "qa.err.malformed_response":"Неожиданный ответ", "qa.err.no_data":"Модели не получены", "qa.err.no_catalog_match":"Нет совпадений с каталогом", "qa.err.server_error":"Ошибка сервера AA", "qa.err.connection_failed":"Ошибка подключения", "auth.tagline":"Один шлюз. Все модели ИИ.", "auth.welcome":"С возвращением", "auth.subtitle":"Войдите в консоль администратора этой установки GeekCubo.", "auth.api_key":"API-ключ", "auth.continue":"Продолжить", "nav.search":"Поиск", "nav.overview":"Обзор", "nav.providers":"Провайдеры", "nav.routing":"Маршрутизация ИИ", "nav.analytics":"Аналитика", "nav.api_keys":"API-ключи", "nav.help_docs":"Помощь и документация", "nav.sign_out":"Выйти", "status.connected":"Подключено", "status.disconnected":"Отключено", "auth.checking":"Проверка…", "auth.welcome_aboard":"Добро пожаловать.", "auth.key_invalid":"Ключ не подошел. Проверьте префикс sk-geek-…", "tab.overview.title":"Обзор", "tab.overview.sub":"Ваш single-tenant маршрутизатор LLM в одном экране.", "tab.providers.title":"Ключи провайдеров", "tab.providers.sub":"BYOK — шифруются при хранении, используются для вызова внешних LLM.", "tab.routing.title":"Маршрутизация", "tab.routing.sub":"Как model='auto' выбирает подходящую модель для каждого запроса.", "tab.analytics.title":"Аналитика", "tab.analytics.sub":"Локальные расходы, задержка и история запросов.", "tab.keys.title":"API-ключи", "tab.keys.sub":"Ключи sk-geek-*, аутентифицирующие трафик вывода из SDK и CLI.", "nav.quality":"Качество", "tab.quality.title":"Оценки качества", "tab.quality.sub":"Реальные результаты бенчмарков для стратегии маршрутизации по качеству. Источник — Artificial Analysis.", "auth.username":"Имя пользователя", "auth.password":"Пароль", "auth.sign_in":"Войти", "nav.security":"Безопасность", "tab.security.title":"Безопасность", "tab.security.sub":"Учётная запись администратора, пароль и сеансы.", "tab.profiles.title":"Профили маршрутизации", "tab.profiles.sub":"Именованные конфигурации Auto, которые клиенты выбирают по id модели.", "tab.integrations.title":"Подключить инструмент", "tab.integrations.sub":"Готовая конфигурация для OpenCode, Claude Code, Cursor и других.", "tab.intelligence.title":"Данные моделей", "tab.intelligence.sub":"Откуда берутся цены и лимиты моделей.", "auth.loading":"Загрузка…", "auth.checking_status":"Проверка статуса администратора.", "auth.signin_title":"Вход", "auth.signin_sub":"Доступ администратора к этой установке GeekCubo.", "auth.forgot":"Забыли пароль?", "auth.reset_hint":"Сбросьте его на хосте или в контейнере:", "auth.reset_note":"Ключи, провайдеры и статистика не затрагиваются.", "auth.setup_title":"Создать учётную запись администратора", "auth.setup_sub":"Управляет этой установкой GeekCubo: ключи провайдеров, API-ключи и маршрутизация.", "auth.min_password":"Не менее 8 символов", "auth.confirm_password":"Подтвердите пароль", "auth.setup_token":"Токен установки", "auth.from_log":"Из журнала сервера", "auth.create_admin":"Создать администратора", "auth.where_token":"Где взять токен установки?", "auth.token_hint":"Печатается в журнале сервера при первом запуске. Чтобы выпустить новый:", "auth.toggle_password":"Показать или скрыть пароль", "ov.spend":"Расходы (7 дн.)", "ov.savings":"Экономия маршрутизации", "ov.p50":"задержка p50", "ov.models":"Доступные модели", "ov.quickstart":"Быстрый старт", "ov.recent":"Последняя активность", "prov.title":"Ключи провайдеров", "prov.tab_std":"Стандартные провайдеры", "prov.tab_custom":"Свои провайдеры", "routing.strategy":"Стратегия маршрутизации", "routing.pools":"Пулы моделей", "routing.advanced":"Резерв, эскалация и непрерывность", "routing.explain":"Проверить решение маршрутизации", "profiles.title":"Профили маршрутизации", "int.title":"Подключить ИИ-инструмент", "md.title":"Источники данных о моделях", "md.lookup":"Поиск цены", "an.spend":"Расходы по моделям", "an.latency":"Задержка по провайдерам", "an.recent":"Последние запросы", "keys.title":"API-ключи маршрутизатора", "sec.sessions":"Сеансы", "q.setup":"Настроить оценку качества", "q.models":"Модели", "preset.heading":"Начать с шаблона", "preset.sub":"Шаблон открывается в редакторе уже заполненным — измените что нужно перед сохранением.", "preset.economy":"Самая дешёвая подходящая модель на каждый запрос. Минимальные расходы, без порога качества.", "preset.premium":"Сначала самые сильные модели, цена не важна. Для задач, где качество важнее.", "preset.coding":"Вызовы инструментов и длинные запросы уходят в пул Hard. Для агентов и редакторов.", "preset.fast":"Сбалансированная маршрутизация с упором на низкую задержку.", "ui.profiles":"Профили", "ui.security":"Безопасность", "ui.api_keys":"API-ключи", "ui.connect_a_tool":"Подключить инструмент", "ui.model_data":"Данные моделей", "ui.connecting":"Подключение…", "ui.language":"Язык", "ui.light":"Светлая", "ui.system":"Системная", "ui.dark":"Тёмная", "ui.openai_compatible_base_url":"Базовый URL, совместимый с OpenAI", "ui.copy":"Копировать", "ui.use_this_in_any_openai_compatible_client":"Используйте в любом клиенте, совместимом с OpenAI.", "ui.signed_in":"Выполнен вход", "ui.security_and_sessions":"Безопасность и сеансы", "ui.api_keys_2":"API-ключи", "ui.sign_out":"Выйти", "ui.you_re_up_point_any_openai_sdk_at_your_b":"Всё готово — направьте любой OpenAI SDK на ваш базовый URL.", "ui.last_5_requests_routed_through_this_serv":"Последние 5 запросов, прошедших через этот сервер.", "ui.view_all":"Показать все", "ui.no_requests_yet":"Запросов пока нет.", "ui.new_here_get_fully_set_up_in_2_minutes":"Впервые здесь? Полная настройка за 2 минуты", "ui.re_enter_as_a_named_provider":"Ввести заново как именованного провайдера", "ui.remove_legacy_entry":"Удалить устаревшую запись", "ui.provider":"Провайдер", "ui.others_openai_format":"Другие (формат OpenAI)", "ui.api_key":"API-ключ", "ui.provider_name":"Имя провайдера", "ui.display_name_a_unique_internal_slug_is_d":"Отображаемое имя. Уникальный внутренний slug создаётся автоматически.", "ui.api_base_url":"Базовый URL API", "ui.usually_ends_in_v1_must_be_https_unless_":"Обычно оканчивается на /v1. Должен быть https, если хост не указан в CUSTOM_PROVIDER_ALLOWED_LOCAL_HOSTS.", "ui.api_key_2":"API-ключ", "ui.encrypted_at_rest_never_displayed_again_":"Шифруется при хранении. После сохранения больше не показывается.", "ui.prefix":"Префикс", "ui.status":"Статус", "ui.no_provider_keys_yet":"Ключей провайдеров пока нет", "ui.add_at_least_one_to_start_routing_real_t":"Добавьте хотя бы один, чтобы направлять реальный трафик. Выберите провайдера выше или нажмите быстрый вариант.", "ui.lowest_cost_that_clears_your_quality_flo":"Наименьшая стоимость, превышающая ваш порог качества. Безопасный выбор при любом числе провайдеров.", "ui.recommended":"Рекомендуется", "ui.lowest_per_token_cost_meeting_the_reques":"Наименьшая стоимость за токен при соблюдении требований запроса. Качество вывода может различаться.", "ui.highest_score_from_artificial_analysis_o":"Наивысший балл из Artificial Analysis или ваших ручных переопределений. Без баллов используется цена как приближение.", "ui.re_ranks_by_observed_success_rate_and_la":"Переранжирует по наблюдаемым успешности и задержке, когда у модели наберётся 20+ запросов здесь. До этого: «Сбалансированный».", "ui.sends_each_request_to_your_mundane_or_ha":"Направляет каждый запрос в пул Mundane или Hard по наблюдаемым признакам (инструменты, размер, длина).", "ui.highest_throughput_and_lowest_first_toke":"Наибольшая пропускная способность и наименьшая задержка первого токена по бенчмаркам. Сохранено для совместимости.", "ui.legacy":"Устаревший", "ui.registered_models":"Зарегистрированные модели", "ui.show":"Показать", "ui.deployable":"Разворачиваемые", "ui.custom_providers":"Свои провайдеры", "ui.model":"Модель", "ui.capabilities":"Возможности", "ui.context":"Контекст", "ui.price_1m_in_out":"Цена /1M (вход · выход)", "ui.availability":"Доступность", "ui.pools":"Пулы", "ui.previous":"Назад", "ui.next":"Далее", "ui.fallback_and_escalation_always_keep_the_":"Резервирование и эскалация всегда сохраняют требуемые возможности запроса. Решения принимаются до начала запроса; модель никогда не меняется посреди потока.", "ui.maximum_attempts_primary_fallbacks":"Максимум попыток (основная + резервные)", "ui.what_counts_as_retryable":"Что считается повторяемым", "ui.quality_floor_percentile_0_off":"Порог качества (перцентиль, 0 = выкл.)", "ui.needs_quality_scores_ignored_and_reporte":"Нужны оценки качества; без них параметр игнорируется (и это сообщается).", "ui.what_the_quality_floor_does":"Что делает порог качества", "ui.balanced_weighs_price_against_quality_th":"«Сбалансированный» сопоставляет цену и качество. Порог исключает модели ниже этого перцентиля, поэтому очень дешёвая, но слабая модель не победит. Поставьте 0, чтобы отключить порог.", "ui.messages":"Сообщений ≥", "ui.prompt_characters":"Символов запроса ≥", "ui.how_request_signals_are_measured":"Как измеряются признаки запроса", "ui.mode":"Режим", "ui.off":"Выкл.", "ui.manual_client_sends_x_geek_escalate":"Вручную (клиент отправляет x-geek-escalate)", "ui.auto_after_repeated_upstream_failures":"Автоматически (после повторных сбоев провайдера)", "ui.failures_before_escalating":"Сбоев до эскалации", "ui.max_escalations_per_conversation":"Макс. эскалаций на диалог", "ui.destination_pool":"Целевой пул", "ui.when_escalation_triggers":"Когда срабатывает эскалация", "ui.remember_for_minutes":"Помнить (минут)", "ui.what_continuity_does":"Что делает непрерывность", "ui.save_routing_policy":"Сохранить политику маршрутизации", "ui.dry_run_shows_which_model_auto_would_cho":"Пробный прогон: показывает, какую модель выберет Auto и почему. Наверх ничего не отправляется.", "ui.messages_2":"Сообщений", "ui.prompt_chars":"Символов запроса", "ui.explain":"Объяснить", "ui.three_filters_applied_in_order":"Три фильтра, применяемые по порядку.", "ui.how_each_strategy_maps_to_litellm_router":"Как каждая стратегия соответствует LiteLLM Router", "ui.strategy":"Стратегия", "ui.import_json":"Импорт JSON", "ui.new_profile":"Новый профиль", "ui.generates_configuration_that_points_a_cl":"Создаёт конфигурацию, направляющую клиент на этот GeekCubo. Ключи подставляются через переменные окружения и никогда не встраиваются.", "ui.search_tools":"Поиск инструментов", "ui.routing_profile_or_model":"Профиль маршрутизации или модель", "ui.endpoint":"Конечная точка", "ui.format":"Формат", "ui.download":"Скачать", "ui.add_source":"Добавить источник", "ui.name":"Название", "ui.https_url_models_dev_compatible_json":"HTTPS-адрес (JSON, совместимый с models.dev)", "ui.save_source":"Сохранить источник", "ui.cancel":"Отмена", "ui.shows_what_each_enabled_source_reports_f":"Показывает, что каждый включённый источник сообщает о модели и какое значение выберет GeekCubo. Ваши собственные цены всегда в приоритете.", "ui.look_up":"Найти", "ui.routing":"Маршрутизация", "ui.volume":"Объём", "ui.routing_decisions":"Решения маршрутизации", "ui.how_auto_requests_were_classified_and_wh":"Как классифицировались запросы Auto и куда они направлялись.", "ui.by_tier":"По уровню", "ui.by_strategy":"По стратегии", "ui.by_routing_id":"По ID маршрутизации", "ui.top_models_served":"Самые обслуживаемые модели", "ui.reliability":"Надёжность", "ui.errors_by_cause":"Ошибки по причинам", "ui.compare_against_a_baseline_model":"Сравнить с базовой моделью", "ui.none":"Нет", "ui.compare":"Сравнить", "ui.how_the_comparison_is_calculated":"Как рассчитывается сравнение", "ui.p50_and_p99_sourced_from_local_request_l":"p50 и p99 — из локальных журналов запросов.", "ui.requests":"Запросы", "ui.newest_first_click_a_row_to_copy_its_tra":"Сначала новые. Нажмите на строку, чтобы скопировать trace ID.", "ui.when":"Когда", "ui.tokens_in_out":"Токены (вход / выход)", "ui.latency":"Задержка", "ui.no_traffic_yet":"Трафика пока нет", "ui.once_you_start_sending_requests_they_ll_":"Как только вы начнёте отправлять запросы, они появятся здесь в реальном времени.", "ui.expires":"Истекает", "ui.never":"Никогда", "ui.7_days":"7 дней", "ui.30_days":"30 дней", "ui.90_days":"90 дней", "ui.1_year":"1 год", "ui.use_it_with_opencode":"Использование с OpenCode:", "ui.created":"Создан", "ui.last_used":"Последнее использование", "ui.actions":"Действия", "ui.no_api_keys":"Нет API-ключей", "ui.generate_one_above_to_start_sending_requ":"Создайте ключ выше, чтобы отправлять запросы из SDK или CLI.", "ui.administrator":"Администратор", "ui.the_single_local_account_that_controls_t":"Единственная локальная учётная запись, управляющая этой установкой.", "ui.password_was_reset_from_the_command_line":"Пароль был сброшен из командной строки", "ui.change_password":"Изменить пароль", "ui.current_password":"Текущий пароль", "ui.new_password":"Новый пароль", "ui.confirm_new_password":"Подтвердите новый пароль", "ui.update_password":"Обновить пароль", "ui.signed_in_browsers_for_this_administrato":"Браузеры, вошедшие под этим администратором. Сеансы истекают через 12 часов или 60 минут бездействия.", "ui.log_out_all_other_sessions":"Выйти во всех остальных сеансах", "ui.device":"Устройство", "ui.last_active":"Последняя активность", "ui.local_recovery":"Локальное восстановление", "ui.password_recovery_is_local_only_by_desig":"Восстановление пароля намеренно только локальное — нет сброса по почте и нет публичного endpoint, который мог бы сменить пароль.", "ui.open_a_shell_where_geekcubo_runs_host_or":"Откройте оболочку там, где работает GeekCubo (хост или контейнер).", "ui.choose_a_new_password_at_the_prompt_all_":"Задайте новый пароль в приглашении. Все сеансы панели будут завершены; API-ключи, провайдеры и данные об использовании не затрагиваются.", "ui.artificial_analysis_api_key":"API-ключ Artificial Analysis", "ui.optional":"(необязательно)", "ui.save_key":"Сохранить ключ", "ui.remove_stored_key":"Удалить сохранённый ключ", "ui.how_quality_scoring_works":"Как работает оценка качества", "ui.paste_it_above_and_save_it_is_encrypted_":"Вставьте ключ выше и сохраните. Он шифруется при хранении, а уже закешированные данные отбрасываются, чтобы следующее обновление использовало новый ключ.", "ui.quality_scores":"Оценки качества", "ui.where_these_numbers_come_from":"Откуда эти числа", "ui.manual":"Вручную", "ui.effective":"Итоговое", "ui.m_blended":"$/M суммарно", "ui.help_and_docs":"Помощь и документация", "ui.what_is_geekcubo":"Что такое GeekCubo?", "ui.60_second_quickstart":"Быстрый старт за 60 секунд", "ui.keyboard_shortcuts":"Горячие клавиши", "ui.switch_tabs":"Переключение вкладок", "ui.command_palette":"Палитра команд", "ui.toggle_this_help":"Показать/скрыть эту справку", "ui.close_drawers_palette":"Закрыть панели / палитру", "ui.going_further":"Дальше", "js.ov_empty_a":"Запросов пока нет.", "js.ov_empty_b":"Как только вы отправите первый вызов, он появится здесь.", "js.ra_unavailable":"Аналитика маршрутизации недоступна.", "js.no_spend":"За этот период расходов пока нет.", "js.no_traffic":"Трафика пока нет", "toast.copied":"Скопировано в буфер обмена", "toast.copy_blocked":"Не удалось скопировать — браузер заблокировал", "toast.signed_in":"Вход выполнен как {name}", "toast.admin_created":"Администратор {name} создан", "toast.signed_out":"Выход выполнен", "toast.load_providers_failed":"Не удалось загрузить провайдеров: {msg}", "toast.removed_provider":"{name} удалён", "toast.api_key_empty":"API-ключ не может быть пустым", "toast.saved_provider":"Ключ {name} сохранён", "toast.load_custom_failed":"Не удалось загрузить свои провайдеры: {msg}", "toast.updated":"{name} обновлён", "toast.model_id_empty":"ID модели не может быть пустым", "toast.model_id_dup":"Такой ID модели уже зарегистрирован", "toast.model_saved":"Модель сохранена", "toast.select_one_model":"Выберите хотя бы одну новую модель", "toast.added_models_one":"Добавлена 1 модель", "toast.added_models_many":"Добавлено моделей: {count}", "toast.load_routing_failed":"Не удалось загрузить маршрутизацию: {msg}", "toast.routing_strategy":"Стратегия маршрутизации: {name}", "toast.policy_saved":"Политика маршрутизации сохранена", "toast.load_models_failed":"Не удалось загрузить модели: {msg}", "toast.load_analytics_failed":"Не удалось загрузить аналитику: {msg}", "toast.load_keys_failed":"Не удалось загрузить ключи: {msg}", "toast.revoked":"{name} отозван", "toast.name_empty":"Имя не может быть пустым", "toast.key_renamed":"Ключ переименован", "toast.name_first":"Сначала дайте ключу имя", "toast.created":"{name} создан", "toast.load_security_failed":"Не удалось загрузить безопасность: {msg}", "toast.password_updated":"Пароль обновлён — другие устройства вышли", "toast.load_quality_failed":"Не удалось загрузить оценки качества: {msg}", "toast.score_range":"Оценка должна быть числом от 0 до 100", "toast.override_set":"Переопределение задано для {name}", "toast.reset":"{name} сброшен", "toast.aa_saved":"Ключ Artificial Analysis сохранён", "toast.stored_removed":"Сохранённый ключ удалён", "toast.remove_key_failed":"Не удалось удалить ключ: {msg}", "toast.aa_refreshed":"Оценки Artificial Analysis обновлены", "toast.refresh_failed":"Не удалось обновить: {msg}", "toast.load_profiles_failed":"Не удалось загрузить профили: {msg}", "toast.duplicated":"{name} продублирован", "toast.now_default":"{name} теперь по умолчанию", "toast.deleted":"{name} удалён", "toast.default_reassigned":" — по умолчанию теперь auto", "toast.saved_profile":"{name} сохранён", "toast.file_too_large":"Этот файл слишком велик для экспорта профиля.", "toast.load_integrations_failed":"Не удалось загрузить интеграции: {msg}", "toast.load_mi_failed":"Не удалось загрузить источники данных: {msg}", "toast.source_added":"Источник добавлен", "toast.legacy_removed":"Устаревшая запись «__custom__» удалена", "toast.saved_as":"Сохранено {name} как {slug}. Получите его модели ниже.", "confirm.remove_provider":"Удалить ключ {name}? Запросы к {name} начнут завершаться ошибкой.", "confirm.remove_model":"Удалить модель {name}?", "confirm.remove_custom":"Удалить провайдера «{name}» и его модели?", "confirm.sign_out_others":"Выйти во всех остальных браузерах этого администратора?", "confirm.reset_score":"Сбросить {name} к оценке AA?", "confirm.remove_aa_key":"Удалить сохранённый ключ Artificial Analysis? Ключ из окружения снова вступит в силу, если задан.", "confirm.change_slug":"Изменить API-идентификатор с «{old}» на «{new}»?\n\nВсе клиенты, отправляющие model: «{old}», перестанут работать.", "confirm.delete_source":"Удалить этот источник метаданных?", "confirm.legacy_remove":"Навсегда удалить устаревший ключ провайдера «__custom__» ({prefix})?\n\nОн не используется для маршрутизации. Сохраните ключ в другом месте, если ещё нужен — восстановить нельзя.", "confirm.revoke":"Отозвать «{name}»?\n\nКлиенты с этим ключом сразу получат 401. Необратимо — выдайте новый ключ, если доступ понадобится снова.", "confirm.rotate":"Ротировать «{name}»?\n\nБудет создан и показан один раз ключ замены с теми же ограничениями.\n\nOK = отозвать старый ключ сейчас (немедленный переход).\nОтмена = оставить старый ключ до ручного отзыва.", "prompt.rename_key":"Переименовать ключ «{name}» в:", "prompt.set_score":"Задать ручную оценку качества для {name} (0-100):", "prompt.aa_current":"Текущая оценка AA: {score}", "prompt.override_note":"Необязательная заметка (почему переопределяете?):", "auth.session_expired":"Сеанс истёк. Войдите снова.", "auth.enter_creds":"Введите имя пользователя и пароль.", "auth.creds_required":"Требуются имя пользователя и пароль.", "auth.pw_mismatch":"Пароли не совпадают.", "auth.paste_token":"Вставьте одноразовый токен установки из журнала сервера.", "auth.signed_out":"Выполнен выход.", "auth.pw_match":"Пароли совпадают.", "auth.pw_mismatch_yet":"Пароли пока не совпадают.", "auth.new_pw_mismatch":"Новые пароли не совпадают.", "auth.fill_three":"Заполните все три поля.", "qa.connection":"Подключение к Artificial Analysis", "qa.test":"Проверить подключение", "qa.replace":"Заменить ключ", "qa.add":"Добавить ключ", "qa.remove":"Удалить ключ", "qa.last_sync":"Последняя успешная синхронизация", "qa.last_error":"Последняя ошибка", "qa.never":"ещё не синхронизировано", "qa.from_env":"из окружения", "qa.saving":"Сохранение…", "qa.key_hint":"Шифруется на этом сервере и больше не показывается. Предыдущий ключ остаётся активным, пока не сохранён этот.", "qa.daily_limit_label":"Дневной лимит ключа", "qa.daily_limit_hint":"Запросов за 24 часа, согласно странице аккаунта Artificial Analysis. Оставьте пустым для документированного лимита 100/день.", "qa.status.not_configured":"Не настроено", "qa.status.connected":"Подключено", "qa.status.invalid_key":"Неверный ключ", "qa.status.rate_limited":"Лимит исчерпан", "qa.status.connection_failed":"Ошибка подключения", "qa.status.cached":"Кэшированные данные", "pricing.legend":"Цены", "pricing.allow_estimates":"Разрешить справочные оценки в Auto, «Самый дешёвый» и лимитах стоимости", "pricing.allow_estimates_help":"По умолчанию выключено. Сравниваются только подтверждённые цены провайдера; модели только со справочной оценкой не участвуют в Auto. При включении каждое решение на основе оценки помечается.", "confirm.bulk_remove_models":"Удалить выбранные модели ({count})? pinned-запросы к ним начнут завершаться ошибкой.", "nav.chat":"Чат", "tab.chat.title":"Чат", "tab.chat.sub":"Общайтесь с развёрнутыми моделями. Маршрутизация, кэш и учёт — как у трафика SDK.", "ui.open_chat":"Открыть чат", "ui.open_chat_hint":"Общайтесь с развёрнутыми моделями из браузера — та же маршрутизация, кэш и учёт затрат, что у SDK-трафика.", "chat.new":"Новый чат", "chat.settings_title":"Настройки чата", "chat.default_title":"Новый чат", "chat.clear_history":"Очистить историю…", "chat.conversations_aria":"Диалоги", "chat.model_aria":"Модель", "chat.regenerate":"Сгенерировать ответ заново", "chat.empty_title":"Спросите о чём угодно.", "chat.empty_sub":"Запросы идут через движок — та же маршрутизация, кэш и учёт затрат, что у SDK-трафика.", "chat.input_placeholder":"Сообщение GeekCubo…", "chat.send":"Отправить", "chat.stop":"Стоп", "chat.system_prompt":"Системный промпт…", "chat.system_prompt_set":"Системный промпт ✓", "chat.system_ph":"Вы полезный ассистент…", "chat.system_help":"Пусто = использовать значение чата по умолчанию. Сохраняется для диалога.", "chat.save_prompt":"Сохранить промпт", "chat.default_model":"Модель по умолчанию", "chat.default_model_help":"Используется для новых диалогов. Собственный выбор диалога имеет приоритет.", "chat.temperature":"Температура", "chat.max_tokens":"Макс. токенов вывода", "chat.default_system_prompt":"Системный промпт по умолчанию", "chat.default_system_prompt_ph":"Вы лаконичный инженерный ассистент.", "chat.default_system_help":"Применяется к диалогам без собственного промпта.", "chat.save_history":"Сохранять историю чата на этом сервере", "chat.retention_days":"Хранить диалоги (дней)", "chat.retention_help":"Более старые диалоги удаляются. Пусто — хранить всё.", "chat.font_size":"Размер текста сообщений", "chat.fs_small":"Мелкий", "chat.fs_medium":"Средний", "chat.fs_large":"Крупный", "chat.enter_to_send":"Enter отправляет сообщение", "chat.privacy_note":"Диалоги хранятся в базе данных этого сервера. Запросы отправляются настроенным провайдерам — точно как SDK-трафик.", "chat.privacy_ack":"Я понимаю, что трафик чата отправляется настроенным провайдерам", "chat.save_settings":"Сохранить настройки", "chat.model_auto":"Авто (выбирает роутер)", "chat.no_conversations":"Пока нет диалогов.", "chat.delete_convo_title":"Удалить этот диалог", "chat.kbd_enter_send":"Enter — отправить · Shift+Enter — новая строка", "chat.kbd_ctrl_enter_send":"Ctrl+Enter — отправить · Enter — новая строка", "chat.tokens_meta":"{in} вход · {out} выход", "chat.error_note":"Генерация остановилась до завершения.", "chat.upstream_error":"Upstream-модель вернула ошибку.", "toast.chat_load_failed":"Не удалось загрузить данные чата: {msg}", "toast.chat_failed":"Ошибка запроса чата: {msg}", "toast.chat_convo_deleted":"Диалог удалён", "toast.chat_cleared":"Удалено диалогов: {count}", "toast.chat_temp_range":"Температура должна быть от 0 до 2", "toast.chat_settings_saved":"Настройки чата сохранены", "toast.chat_open_convo":"Сначала откройте диалог", "toast.chat_saved_prompt":"Системный промпт для этого диалога сохранён", "confirm.delete_conversation":"Удалить этот диалог?\n\nСообщения будут удалены из базы данных сервера. Записи об использовании и затратах останутся в аналитике.", "confirm.clear_chat_history":"Удалить ВСЕ сохранённые диалоги?\n\nВсе сообщения чата на этом сервере будут удалены. Записи об использовании и затратах останутся в аналитике.", "q.ov_score":"Ручная оценка (0–100)", "q.ov_note":"Заметка", "q.ov_model_ph":"напр. openai/gpt-4o, anthropic/claude-…", "q.ov_note_ph":"Почему заменяет оценку AA", "q.ov_apply":"Применить замену", "q.ov_clear":"Убрать замену", "q.ov_help":"Один или несколько id моделей через запятую — замена применяется ко всем перечисленным моделям. Ручные оценки всегда важнее оценок AA.", "toast.q_ids_required":"Введите хотя бы один id модели", "toast.q_too_many":"Массовая операция ограничена 500 id моделей", "toast.q_bulk_set":"Замены установлены для {count} моделей", "toast.q_bulk_clear":"Замены удалены для {count} моделей", "providers.bulk_actions":"Массовые действия с моделями", "providers.select_all":"Выбрать все", "providers.selected_count":"Выбрано: {count}", "providers.bulk_capability":"Возможность", "providers.bulk_capability_state":"Состояние возможности", "providers.cap_tools":"Инструменты", "providers.cap_vision":"Зрение", "providers.cap_supported":"Поддерживается", "providers.cap_unsupported":"Не поддерживается", "providers.cap_unknown":"Неизвестно", "providers.cap_catalog":"Использовать каталог", "providers.cap_json_mode":"Режим JSON", "providers.cap_json_schema":"JSON-схема", "providers.apply":"Применить", "providers.enable":"Включить", "providers.disable":"Отключить", "providers.remove_selected":"Удалить выбранные", "providers.resolve_metadata":"Сверить", "toast.metadata_resolved":"Метаданные: {resolved} сопоставлено, {ambiguous} неоднозначно, {unmatched} без совпадений, {failed} ошибок.", "select.search_ph":"Поиск ключей каталога…", "providers.catalog_key_ph":"Поиск ключей каталога…", "select.remove_item":"Убрать {name}", "select.use_custom":"Использовать «{name}»", "select.no_matches":"Нет подходящих моделей", "select.more_results":"Ещё {count} — продолжайте ввод для уточнения", "q.ov_model_search_ph":"Найдите и выберите модели…", "q.ov_help_picker":"Найдите и выберите одну или несколько моделей или отметьте строки в таблице ниже. Ручные оценки всегда важнее оценок AA.", "q.filter_ph":"Фильтр моделей…", "q.select_filtered":"Выбрать отфильтрованные", "q.select_all_filtered":"Выбрать все отфильтрованные модели", "q.deselect_all":"Снять выбор", "q.bulk_set":"Задать оценку выбранным", "q.bulk_clear":"Сбросить выбранные переопределения", "q.select_model":"Выбрать {name}", "confirm.q_bulk_clear":"Сбросить ручные переопределения для {count} выбранных моделей?", "qa.daily_limit_short":"Дневной лимит", "chat.attach":"Прикрепить файлы", "chat.attach_drop":"Перетащите файлы, чтобы прикрепить", "chat.attach_remove":"Удалить вложение", "chat.attach_unreadable":"Не удалось прочитать файл; будет отправлено только его имя.", "chat.attach_uploading":"Загрузка…", "chat.attach_too_large":"Слишком большой (макс. {max} МБ)", "toast.chat_attach_failed":"Не удалось прикрепить {name}: {msg}", "toast.chat_attach_disabled":"Вложения отключены на этом сервере.", "toast.chat_attach_too_many":"Не более {max} вложений на сообщение.", "toast.chat_attach_extract_failed":"{name}: не удалось прочитать ({msg})", "toast.chat_attach_wait":"Дождитесь завершения загрузки.", "chat.search_toggle":"Поиск в интернете", "chat.search_settings":"Поиск в интернете", "chat.search_help":"Когда включено, GeekCubo ищет в интернете перед ответом и ссылается на использованные страницы. Результаты добавляются как системное сообщение, поэтому их может использовать любая модель.", "chat.search_mode":"Режим поиска", "chat.search_mode_off":"Выключен", "chat.search_mode_manual":"Вручную (для каждого сообщения)", "chat.search_mode_auto":"Автоматически (зарезервировано)", "chat.search_mode_help":"В ручном режиме в поле ввода появляется переключатель. Автоматический режим зарезервирован и пока не реализован.", "chat.search_backend":"Поисковый сервис", "chat.search_backend_none":"Выберите сервис…", "chat.search_backend_searxng":"SearXNG (собственный сервер)", "chat.search_backend_brave":"Поисковый API Brave", "chat.search_backend_tavily":"Tavily", "chat.search_url":"URL SearXNG", "chat.search_url_ph":"http://searxng:8080/", "chat.search_url_help":"Базовый URL вашего экземпляра SearXNG. Профиль search в установщике публикует его во внутренней сети.", "chat.search_api_key":"Ключ API", "chat.search_api_key_ph":"Вставьте новый ключ вместо сохранённого", "chat.search_key_clear":"Удалить сохранённый ключ", "chat.search_key_help":"Хранится на этом сервере в зашифрованном виде и больше не показывается. Brave и Tavily требуют ключ; SearXNG — нет.", "chat.search_max_searches":"Максимум поисков на диалог", "chat.search_max_results":"Результатов на поиск", "chat.search_max_fetches":"Страниц на поиск", "chat.search_timeout":"Тайм-аут поиска (секунды)", "chat.search_test":"Проверить подключение", "chat.search_testing":"Проверка…", "chat.search_test_ok":"{count} результатов за {ms} мс", "chat.search_test_failed":"Проверка поиска не удалась: {msg}", "chat.search_key_state_unset":"Ключ не сохранён", "chat.search_key_state_set":"Ключ сохранён", "chat.search_key_state_undecryptable":"Сохранённый ключ не расшифровывается", "chat.context_budget":"Контекст: {tokens} / {budget} токенов", "chat.context_omitted":"Пропущено {count} предыдущих сообщений", "chat.sources":"Источники", "chat.search_used":"поиск в интернете: {backend}", "toast.search_saved":"Настройки поиска в интернете сохранены", "toast.search_save_failed":"Не удалось сохранить настройки поиска: {msg}", "toast.search_test_failed":"Проверка поиска в интернете не удалась", "nav.local":"Локальный ИИ", "tab.local.title":"Локальный ИИ", "tab.local.sub":"Обслуживайте модели со своих машин через этот маршрутизатор.", "local.title":"Подключение локального ИИ", "local.sub":"Маршрутизация к моделям на ваших собственных машинах. Небольшой коннектор сам подключается к этому серверу, поэтому порты не открываются и входящий туннель не нужен.", "local.refresh":"Обновить", "local.setup_button":"Настроить машину", "local.feature_off_title":"Подключение локального ИИ отключено на сервере", "local.feature_off_body":"Задайте LOCAL_CONNECT_ENABLED=true в окружении сервера и перезапустите его, затем перезагрузите эту страницу.", "local.url_missing_title":"Публичный URL не задан", "local.url_missing_body":"Задайте LOCAL_CONNECT_PUBLIC_URL — адрес, к которому должны подключаться коннекторы (например https://example.com), чтобы команда установки и служебные файлы заполнились.", "local.settings_title":"Поведение маршрутизации", "local.settings_sub":"Определяет, участвуют ли локальные модели в Auto и может ли запрос перейти в облако.", "local.set_enabled":"Разрешить локальные машины для маршрутизации", "local.set_auto":"Включать локальные модели в автоматический выбор", "local.set_no_fallback":"Никогда не переходить в облако при сбое локальной модели", "local.settings_help":"Локальные модели учитываются в Auto только при подтверждённой нулевой цене и если машина одобрена и в сети. При включённом «никогда не переходить» запрос только к локальным моделям завершится ошибкой, а не будет обслужен облачным провайдером.", "local.save_settings":"Сохранить", "local.settings_saved":"Настройки локальной маршрутизации сохранены.", "local.machines_title":"Машины", "local.machines_sub":"Каждая машина — это один коннектор. Ожидающие машины видны, но трафик на них не направляется до одобрения.", "local.machines_empty":"Машин пока нет. Используйте «Настроить машину», чтобы создать код регистрации.", "local.enrollments_title":"Коды регистрации", "local.enrollments_sub":"Одноразовые коды, позволяющие коннектору зарегистрироваться. Код расходуется при первом подключении машины.", "local.new_code":"Новый код", "local.install_title":"Установите коннектор", "local.install_sub":"Выполните это на машине, где размещены ваши модели (Ollama, LM Studio, vLLM, llama.cpp или любой [OI]-совместимый сервер).", "local.service_files":"Запуск как службы", "local.delete":"Удалить", "local.never":"никогда", "local.ctx_suffix":"контекст", "local.ctx_unknown":"контекст неизвестен", "local.no_models":"Эта машина ещё не сообщила ни одной модели.", "local.no_enrollments":"Кодов регистрации нет.", "local.enroll_active":"Активен", "local.enroll_used":"Использован", "local.status_online":"В сети", "local.status_offline":"Не в сети", "local.status_pending":"Ожидает одобрения", "local.status_approved":"Одобрена", "local.status_revoked":"Отозвана", "local.pending_note":"Эта машина ожидает одобрения. Модели перечислены, но трафик на них не направляется.", "local.action_approve":"Одобрить", "local.action_discover":"Найти модели", "local.action_revoke":"Отозвать", "local.action_rotate":"Сменить учётные данные", "local.action_delete":"Удалить", "local.meta_host":"Имя хоста", "local.meta_platform":"Платформа", "local.meta_agent":"Версия коннектора", "local.meta_adapters":"Адаптеры", "local.meta_seen":"Последняя активность", "local.col_model":"Модель", "local.col_adapter":"Тип адаптера", "local.col_context":"Контекст", "local.col_caps":"Возможности", "local.col_enabled":"Включено", "local.kpi_machines":"Машины", "local.kpi_online":"Сейчас в сети", "local.kpi_pending":"Ожидают одобрения", "local.kpi_models":"Модели", "local.toast_approved":"Машина одобрена.", "local.toast_revoked":"Машина отозвана.", "local.toast_deleted":"Машина удалена.", "local.toast_discovered":"Список моделей обновлён.", "local.confirm_revoke":"Отозвать эту машину? Её коннектор будет немедленно отключён и не сможет подключиться, пока вы не смените учётные данные.", "local.confirm_delete_machine":"Удалить эту машину и её список моделей? Это действие необратимо.", "local.confirm_rotate":"Сменить учётные данные этой машины? Работающий коннектор продолжит работу до переподключения, после чего старые данные будут отклонены.", "local.confirm_delete_enrollment":"Удалить этот код регистрации?", "local.credential_once_title":"Скопируйте новые учётные данные сейчас", "local.credential_once_body":"Они показываются только один раз. Сохраните их в конфигурации коннектора на машине.", "local.wizard_title":"Подключить локальную машину", "local.wizard_close":"Закрыть", "local.wizard_back":"Назад", "local.wizard_next":"Далее", "local.wizard_done":"Готово", "local.step1":"Включить", "local.step2":"Код регистрации", "local.step3":"Установка", "local.step4":"Регистрация", "local.step5":"Запуск", "local.step6":"Одобрение", "local.step7":"Модели", "local.step8":"Автомаршрутизация", "local.w0_title":"Включите функцию", "local.w0_body":"Подключение локального ИИ — серверная функция. Её нужно включить, прежде чем коннекторы смогут регистрироваться.", "local.w0_ready":"Функция включена. Продолжите, чтобы создать код регистрации.", "local.w0_blocked":"На этом сервере функция отключена. Задайте LOCAL_CONNECT_ENABLED=true и перезапустите, затем перезагрузите эту страницу.", "local.w1_title":"Создайте код регистрации", "local.w1_body":"Одноразовый код разрешает регистрацию одному коннектору. Он истекает через короткое время.", "local.w1_name":"Имя машины (необязательно)", "local.w1_name_ph":"напр. office-gpu", "local.w1_name_help":"Метка, чтобы узнать эту машину в списке. Позже её можно переименовать.", "local.w1_created":"Код регистрации создан", "local.w2_title":"Установите пакет коннектора", "local.w2_body":"На машине, где размещены ваши модели, установите коннектор. Требуется Python 3.11 или новее.", "local.w2_note":"Устанавливайте в виртуальное окружение, чтобы изолировать от системных пакетов.", "local.w3_title":"Зарегистрируйте машину", "local.w3_body":"Выполните команду регистрации с кодом из шага 2. Учётные данные записываются в файл конфигурации коннектора.", "local.w3_note":"Код одноразовый. Если он истёк, создайте новый.", "local.w4_title":"Запустите коннектор", "local.w4_body":"Запустите коннектор на переднем плане, чтобы увидеть подключение, затем переведите его в службу.", "local.w4_note":"Коннектор держит одно исходящее соединение WebSocket и автоматически переподключается.", "local.w5_title":"Дождитесь появления машины", "local.w5_body":"Как только коннектор подключится, машина появится здесь. Обновите, если это займёт время.", "local.w5_seen":"{name} подключилась.", "local.w5_waiting":"Пока ни одна машина не подключилась.", "local.w5_recheck":"Проверить снова", "local.w6_title":"Одобрите машину", "local.w6_body":"Новая машина остаётся в ожидании, пока администратор её не одобрит. До этого на неё ничего не направляется.", "local.w6_none":"Пока нет машины для одобрения.", "local.w6_must_approve":"Одобрите ожидающую машину, прежде чем продолжить.", "local.w7_title":"Включите локальные модели в Auto", "local.w7_body":"Включите «Включать локальные модели в автоматический выбор» и активируйте нужные модели. Локальные модели выбираются для Auto только при подтверждённой нулевой цене.", "local.w7_done":"Настройка завершена. Локальные модели теперь отображаются на страницах провайдеров и маршрутизации." },
  ja: { "q.tabs_label":"品質セクション", "q.tab_models":"モデル", "q.tab_scores":"品質スコア", "q.tab_aa":"Artificial Analysis 接続", "q.col_availability":"利用可否", "q.avail_yes":"利用可能", "q.avail_no":"プロバイダーキーなし", "q.avail_no_title":"このモデルを提供できる設定済みプロバイダーキーがありません。ベンチマークデータがあってもデプロイ可能にはなりません。", "q.sync_title":"ベンチマーク同期", "q.sync_last_ok":"最後に成功した同期", "q.sync_last_attempt":"最新の試行", "q.sync_returned":"AA から返されたモデル数", "q.sync_matched":"カタログと一致", "q.sync_unmatched":"一致なし", "q.sync_overrides":"手動スコア", "q.sync_outcome_ok":"成功", "q.sync_outcome_failed":"失敗", "q.sync_need_key":"ベンチマークスコアを同期するには Artificial Analysis タブでキーを追加してください。手動スコアはキーなしで使えます。", "q.sync_never":"このキーではまだ同期していません。「AA から更新」を使ってください。", "q.sync_no_models":"前回の同期ではモデルが返されませんでした。", "q.status_line":"ベンチマークデータのあるモデル {matched} 件 · 手動スコア {overrides} 件", "q.src.live":"最新", "q.src.stale_cache":"キャッシュ（AA に接続不可）", "q.src.stale_db":"キャッシュ（保存済みスナップショット）", "q.src.error":"同期失敗", "q.src.missing_key":"API キーなし", "q.auto_status":"自動ルーティングの状態", "q.auto_status_hint":"model=\"auto\" が今選ぶモデル。設定済みのプロバイダーに依存し、ベンチマーク同期とは関係ありません。", "q.auto_no_provider":"現在の要件を満たすデプロイ可能なモデルがありません。プロバイダーページでキーを追加してください。これは Artificial Analysis の同期とは別の問題です。", "qa.credential":"API キー", "qa.cred_stored":"このサーバーに保存（暗号化）", "qa.cred_env":"サーバー環境変数から", "qa.last_test":"最後の接続テスト", "qa.last_test_ok":"最後に成功したテスト", "qa.not_tested":"未テスト", "qa.sync_status":"ベンチマーク同期", "qa.tier":"{tier} プラン", "qa.troubleshooting":"接続のトラブルシューティング", "qa.status.key_configured":"キー設定済み", "qa.sync.not_configured":"未設定", "qa.sync.never_synced":"未同期", "qa.sync.synced":"同期済み", "qa.sync.sync_failed":"同期失敗", "qa.err.invalid_key":"無効なキー", "qa.err.insufficient_tier":"プランにこのエンドポイントが含まれていません", "qa.err.endpoint_retired":"エンドポイント廃止", "qa.err.rate_limited":"レート制限", "qa.err.timeout":"タイムアウト", "qa.err.malformed_response":"予期しない応答", "qa.err.no_data":"モデルが返されません", "qa.err.no_catalog_match":"カタログと一致なし", "qa.err.server_error":"AA サーバーエラー", "qa.err.connection_failed":"接続失敗", "auth.tagline":"ひとつのゲートウェイですべての AI モデルへ。", "auth.welcome":"おかえりなさい", "auth.subtitle":"この GeekCubo の管理者コンソールにサインインします。", "auth.api_key":"APIキー", "auth.continue":"続行", "nav.search":"検索", "nav.overview":"概要", "nav.providers":"プロバイダー", "nav.routing":"経路制御", "nav.analytics":"分析", "nav.api_keys":"APIキー", "nav.help_docs":"ヘルプとドキュメント", "nav.sign_out":"サインアウト", "status.connected":"接続済み", "status.disconnected":"未接続", "auth.checking":"確認中…", "auth.welcome_aboard":"ようこそ。", "auth.key_invalid":"キーが無効です。接頭辞 sk-geek- を確認してください…", "tab.overview.title":"概要", "tab.overview.sub":"シングルテナント LLM ルーターの概要。", "tab.providers.title":"プロバイダーキー", "tab.providers.sub":"BYOK — 保存時に暗号化され、上流 LLM 呼び出しに使用。", "tab.routing.title":"ルーティング", "tab.routing.sub":"model='auto' が各リクエストに最適なモデルを選択する方法。", "tab.analytics.title":"分析", "tab.analytics.sub":"ローカル限定のコスト・遅延・リクエスト履歴。", "tab.keys.title":"APIキー", "tab.keys.sub":"SDK と CLI の推論トラフィックを認証する sk-geek-* キー。", "nav.quality":"品質", "tab.quality.title":"品質スコア", "tab.quality.sub":"品質ルーティング戦略で使う実際のベンチマークスコア。Artificial Analysis から取得します。", "auth.username":"ユーザー名", "auth.password":"パスワード", "auth.sign_in":"サインイン", "nav.security":"セキュリティ", "tab.security.title":"セキュリティ", "tab.security.sub":"管理者アカウント、パスワード、セッション。", "tab.profiles.title":"ルーティングプロファイル", "tab.profiles.sub":"クライアントがモデル ID で選ぶ名前付き Auto 設定。", "tab.integrations.title":"ツールを接続", "tab.integrations.sub":"OpenCode、Claude Code、Cursor などでそのまま使える設定。", "tab.intelligence.title":"モデルデータ", "tab.intelligence.sub":"モデルの価格と上限の取得元。", "auth.loading":"読み込み中…", "auth.checking_status":"管理者の状態を確認しています。", "auth.signin_title":"サインイン", "auth.signin_sub":"この GeekCubo インストールへの管理者アクセス。", "auth.forgot":"パスワードをお忘れですか？", "auth.reset_hint":"ホストまたはコンテナでリセットします:", "auth.reset_note":"キー、プロバイダー、使用状況は影響を受けません。", "auth.setup_title":"管理者アカウントを作成", "auth.setup_sub":"この GeekCubo インストールを管理します: プロバイダーの資格情報、API キー、ルーティング。", "auth.min_password":"8 文字以上", "auth.confirm_password":"パスワードの確認", "auth.setup_token":"セットアップトークン", "auth.from_log":"サーバーログから", "auth.create_admin":"管理者を作成", "auth.where_token":"セットアップトークンはどこにありますか？", "auth.token_hint":"初回起動時にサーバーログへ出力されます。新しいものを発行するには:", "auth.toggle_password":"パスワードを表示または非表示", "ov.spend":"支出（7日間）", "ov.savings":"ルーティング削減額", "ov.p50":"p50 レイテンシ", "ov.models":"利用可能モデル", "ov.quickstart":"クイックスタート", "ov.recent":"最近のアクティビティ", "prov.title":"プロバイダーキー", "prov.tab_std":"標準プロバイダー", "prov.tab_custom":"カスタムプロバイダー", "routing.strategy":"ルーティング戦略", "routing.pools":"モデルプール", "routing.advanced":"フォールバック・エスカレーション・継続性", "routing.explain":"ルーティング判断を試す", "profiles.title":"ルーティングプロファイル", "int.title":"AI ツールを接続", "md.title":"モデルデータソース", "md.lookup":"価格検索", "an.spend":"モデル別支出", "an.latency":"プロバイダー別レイテンシ", "an.recent":"最近のリクエスト", "keys.title":"ルーター API キー", "sec.sessions":"セッション", "q.setup":"品質スコアリングを設定", "q.models":"モデル", "preset.heading":"プリセットから始める", "preset.sub":"テンプレートは入力済みでエディターが開きます。保存前に自由に調整できます。", "preset.economy":"リクエストごとに最も安価な対応モデルを選択。支出最小、品質下限なし。", "preset.premium":"最強のモデルを優先し価格は無視。品質重視の作業向け。", "preset.coding":"ツール呼び出しと長いプロンプトは Hard プールへ。エージェントやエディター作業向け。", "preset.fast":"プール内で低レイテンシを優先するバランス型ルーティング。", "ui.profiles":"プロファイル", "ui.security":"セキュリティ", "ui.api_keys":"APIキー", "ui.connect_a_tool":"ツールを接続", "ui.model_data":"モデルデータ", "ui.connecting":"接続中…", "ui.language":"言語", "ui.light":"ライト", "ui.system":"システム", "ui.dark":"ダーク", "ui.openai_compatible_base_url":"OpenAI 互換ベース URL", "ui.copy":"コピー", "ui.use_this_in_any_openai_compatible_client":"OpenAI 互換クライアントで使用できます。", "ui.signed_in":"サインイン済み", "ui.security_and_sessions":"セキュリティとセッション", "ui.api_keys_2":"APIキー", "ui.sign_out":"サインアウト", "ui.you_re_up_point_any_openai_sdk_at_your_b":"準備完了 — 任意の OpenAI SDK をベース URL に向けてください。", "ui.last_5_requests_routed_through_this_serv":"このサーバーが処理した直近 5 件のリクエスト。", "ui.view_all":"すべて表示", "ui.no_requests_yet":"まだリクエストはありません。", "ui.new_here_get_fully_set_up_in_2_minutes":"初めてですか？2 分ですべて設定できます", "ui.re_enter_as_a_named_provider":"名前付きプロバイダーとして再入力", "ui.remove_legacy_entry":"旧エントリを削除", "ui.provider":"プロバイダー", "ui.others_openai_format":"その他（OpenAI 形式）", "ui.api_key":"APIキー", "ui.provider_name":"プロバイダー名", "ui.display_name_a_unique_internal_slug_is_d":"表示名。内部用の一意なスラッグは自動生成されます。", "ui.api_base_url":"APIベースURL", "ui.usually_ends_in_v1_must_be_https_unless_":"通常は /v1 で終わります。ホストが CUSTOM_PROVIDER_ALLOWED_LOCAL_HOSTS にない限り https が必要です。", "ui.api_key_2":"APIキー", "ui.encrypted_at_rest_never_displayed_again_":"保存時に暗号化され、以後表示されることはありません。", "ui.prefix":"プレフィックス", "ui.status":"状態", "ui.no_provider_keys_yet":"プロバイダーキーはまだありません", "ui.add_at_least_one_to_start_routing_real_t":"実際のトラフィックを流すには 1 つ以上追加してください。上でプロバイダーを選ぶか、クイック追加をクリックします。", "ui.lowest_cost_that_clears_your_quality_flo":"品質下限を満たす中で最も低コスト。プロバイダー数に関係なく安全な既定値です。", "ui.recommended":"推奨", "ui.lowest_per_token_cost_meeting_the_reques":"リクエストの要件を満たす中でトークン単価が最も低い選択。出力品質は変動します。", "ui.highest_score_from_artificial_analysis_o":"Artificial Analysis のスコアまたは手動上書きのうち最高のもの。スコアがない場合は価格を代理指標にします。", "ui.re_ranks_by_observed_success_rate_and_la":"各モデルがここで 20 件以上のリクエストを処理すると、実測の成功率とレイテンシで再ランクします。それまでは「バランス」。", "ui.sends_each_request_to_your_mundane_or_ha":"観測可能なシグナル（ツール、規模、長さ）に基づいて、各リクエストを Mundane または Hard プールへ送ります。", "ui.highest_throughput_and_lowest_first_toke":"ベンチマークデータで最も高いスループットと最も低い初回トークン遅延。既存設定の互換性のため保持しています。", "ui.legacy":"レガシー", "ui.registered_models":"登録モデル", "ui.show":"表示", "ui.deployable":"デプロイ可能", "ui.custom_providers":"カスタムプロバイダー", "ui.model":"モデル", "ui.capabilities":"機能", "ui.context":"コンテキスト", "ui.price_1m_in_out":"価格 /1M（入力 · 出力）", "ui.availability":"可用性", "ui.pools":"プール", "ui.previous":"前へ", "ui.next":"次へ", "ui.fallback_and_escalation_always_keep_the_":"フォールバックとエスカレーションは常にリクエストの必要機能を維持します。判断はリクエスト開始前に行われ、ストリーム途中でモデルが変わることはありません。", "ui.maximum_attempts_primary_fallbacks":"最大試行回数（プライマリ + フォールバック）", "ui.what_counts_as_retryable":"再試行される条件", "ui.quality_floor_percentile_0_off":"品質下限（パーセンタイル、0 = 無効）", "ui.needs_quality_scores_ignored_and_reporte":"品質スコアが必要です。ない場合は無視され、その旨が表示されます。", "ui.what_the_quality_floor_does":"品質下限の役割", "ui.balanced_weighs_price_against_quality_th":"バランスは価格と品質を天秤にかけます。下限を下回るモデルは除外されるため、非常に安価でも弱いモデルは選ばれません。0 にすると下限は無効になります。", "ui.messages":"メッセージ数 ≥", "ui.prompt_characters":"プロンプト文字数 ≥", "ui.how_request_signals_are_measured":"リクエストシグナルの測り方", "ui.mode":"モード", "ui.off":"オフ", "ui.manual_client_sends_x_geek_escalate":"手動（クライアントが x-geek-escalate を送信）", "ui.auto_after_repeated_upstream_failures":"自動（上流の失敗が繰り返された後）", "ui.failures_before_escalating":"エスカレーションまでの失敗回数", "ui.max_escalations_per_conversation":"会話あたりの最大エスカレーション回数", "ui.destination_pool":"移動先プール", "ui.when_escalation_triggers":"エスカレーションの発動条件", "ui.remember_for_minutes":"記憶する期間（分）", "ui.what_continuity_does":"継続性の役割", "ui.save_routing_policy":"ルーティングポリシーを保存", "ui.dry_run_shows_which_model_auto_would_cho":"ドライラン: Auto がどのモデルを選ぶか、その理由を表示します。上流には何も送信されません。", "ui.messages_2":"メッセージ数", "ui.prompt_chars":"プロンプト文字数", "ui.explain":"説明", "ui.three_filters_applied_in_order":"3 つのフィルターを順に適用します。", "ui.how_each_strategy_maps_to_litellm_router":"各戦略が LiteLLM Router にどう対応するか", "ui.strategy":"戦略", "ui.import_json":"JSON をインポート", "ui.new_profile":"新しいプロファイル", "ui.generates_configuration_that_points_a_cl":"この GeekCubo を指すクライアント設定を生成します。キーは環境変数で参照され、埋め込まれることはありません。", "ui.search_tools":"ツールを検索", "ui.routing_profile_or_model":"ルーティングプロファイルまたはモデル", "ui.endpoint":"エンドポイント", "ui.format":"形式", "ui.download":"ダウンロード", "ui.add_source":"ソースを追加", "ui.name":"名前", "ui.https_url_models_dev_compatible_json":"HTTPS URL（models.dev 互換 JSON）", "ui.save_source":"ソースを保存", "ui.cancel":"キャンセル", "ui.shows_what_each_enabled_source_reports_f":"有効な各ソースがそのモデルについて報告する内容と、GeekCubo が採用する値を表示します。自分で設定した価格が常に優先されます。", "ui.look_up":"照会", "ui.routing":"ルーティング", "ui.volume":"量", "ui.routing_decisions":"ルーティング判断", "ui.how_auto_requests_were_classified_and_wh":"Auto リクエストがどう分類され、どこへ送られたか。", "ui.by_tier":"層別", "ui.by_strategy":"戦略別", "ui.by_routing_id":"ルーティング ID 別", "ui.top_models_served":"最も処理されたモデル", "ui.reliability":"信頼性", "ui.errors_by_cause":"原因別エラー", "ui.compare_against_a_baseline_model":"基準モデルと比較", "ui.none":"なし", "ui.compare":"比較", "ui.how_the_comparison_is_calculated":"比較の計算方法", "ui.p50_and_p99_sourced_from_local_request_l":"p50 と p99 — ローカルのリクエストログから算出。", "ui.requests":"リクエスト", "ui.newest_first_click_a_row_to_copy_its_tra":"新しい順。行をクリックすると trace ID をコピーします。", "ui.when":"日時", "ui.tokens_in_out":"トークン（入力 / 出力）", "ui.latency":"レイテンシ", "ui.no_traffic_yet":"まだトラフィックがありません", "ui.once_you_start_sending_requests_they_ll_":"リクエストを送信し始めると、ここにリアルタイムで表示されます。", "ui.expires":"有効期限", "ui.never":"無期限", "ui.7_days":"7 日", "ui.30_days":"30 日", "ui.90_days":"90 日", "ui.1_year":"1 年", "ui.use_it_with_opencode":"OpenCode での使い方:", "ui.created":"作成日", "ui.last_used":"最終使用", "ui.actions":"操作", "ui.no_api_keys":"APIキーがありません", "ui.generate_one_above_to_start_sending_requ":"上で 1 つ生成すると、SDK や CLI からリクエストを送信できます。", "ui.administrator":"管理者", "ui.the_single_local_account_that_controls_t":"このインストールを管理する唯一のローカルアカウントです。", "ui.password_was_reset_from_the_command_line":"パスワードはコマンドラインからリセットされました", "ui.change_password":"パスワードを変更", "ui.current_password":"現在のパスワード", "ui.new_password":"新しいパスワード", "ui.confirm_new_password":"新しいパスワードの確認", "ui.update_password":"パスワードを更新", "ui.signed_in_browsers_for_this_administrato":"この管理者としてサインイン中のブラウザ。セッションは 12 時間、または 60 分間のアイドルで失効します。", "ui.log_out_all_other_sessions":"他のすべてのセッションをログアウト", "ui.device":"デバイス", "ui.last_active":"最終アクティブ", "ui.local_recovery":"ローカル復旧", "ui.password_recovery_is_local_only_by_desig":"パスワード復旧は設計上ローカルのみです — メールによるリセットはなく、パスワードを変更できる公開エンドポイントもありません。", "ui.open_a_shell_where_geekcubo_runs_host_or":"GeekCubo が動作しているホストまたはコンテナでシェルを開きます。", "ui.choose_a_new_password_at_the_prompt_all_":"プロンプトで新しいパスワードを入力します。すべてのダッシュボードセッションがサインアウトされますが、APIキー、プロバイダー、使用状況データは影響を受けません。", "ui.artificial_analysis_api_key":"Artificial Analysis APIキー", "ui.optional":"（任意）", "ui.save_key":"キーを保存", "ui.remove_stored_key":"保存済みキーを削除", "ui.how_quality_scoring_works":"品質スコアリングの仕組み", "ui.paste_it_above_and_save_it_is_encrypted_":"上に貼り付けて保存します。暗号化して保存され、キャッシュ済みの内容は破棄され、次回の更新で新しいキーが使われます。", "ui.quality_scores":"品質スコア", "ui.where_these_numbers_come_from":"これらの数値の出典", "ui.manual":"手動", "ui.effective":"有効値", "ui.m_blended":"$/M 総合", "ui.help_and_docs":"ヘルプとドキュメント", "ui.what_is_geekcubo":"GeekCubo とは？", "ui.60_second_quickstart":"60 秒クイックスタート", "ui.keyboard_shortcuts":"キーボードショートカット", "ui.switch_tabs":"タブを切り替え", "ui.command_palette":"コマンドパレット", "ui.toggle_this_help":"このヘルプの表示切り替え", "ui.close_drawers_palette":"ドロワー / パレットを閉じる", "ui.going_further":"さらに詳しく", "js.ov_empty_a":"まだリクエストはありません。", "js.ov_empty_b":"最初の呼び出しを送信すると、ここに表示されます。", "js.ra_unavailable":"ルーティング分析は利用できません。", "js.no_spend":"この期間の支出はまだ記録されていません。", "js.no_traffic":"まだトラフィックがありません", "toast.copied":"クリップボードにコピーしました", "toast.copy_blocked":"コピーできません — ブラウザにブロックされました", "toast.signed_in":"{name} としてサインインしました", "toast.admin_created":"管理者 {name} を作成しました", "toast.signed_out":"サインアウトしました", "toast.load_providers_failed":"プロバイダーを読み込めません: {msg}", "toast.removed_provider":"{name} を削除しました", "toast.api_key_empty":"APIキーは空にできません", "toast.saved_provider":"{name} のキーを保存しました", "toast.load_custom_failed":"カスタムプロバイダーを読み込めません: {msg}", "toast.updated":"{name} を更新しました", "toast.model_id_empty":"モデル ID は空にできません", "toast.model_id_dup":"そのモデル ID は登録済みです", "toast.model_saved":"モデルを保存しました", "toast.select_one_model":"新しいモデルを 1 つ以上選択してください", "toast.added_models_one":"モデルを 1 件追加しました", "toast.added_models_many":"モデルを {count} 件追加しました", "toast.load_routing_failed":"ルーティングを読み込めません: {msg}", "toast.routing_strategy":"ルーティング戦略: {name}", "toast.policy_saved":"ルーティングポリシーを保存しました", "toast.load_models_failed":"モデルを読み込めません: {msg}", "toast.load_analytics_failed":"分析を読み込めません: {msg}", "toast.load_keys_failed":"キーを読み込めません: {msg}", "toast.revoked":"{name} を失効しました", "toast.name_empty":"名前は空にできません", "toast.key_renamed":"キー名を変更しました", "toast.name_first":"先にキーに名前を付けてください", "toast.created":"{name} を作成しました", "toast.load_security_failed":"セキュリティ設定を読み込めません: {msg}", "toast.password_updated":"パスワードを更新しました — 他の端末をサインアウトしました", "toast.load_quality_failed":"品質スコアを読み込めません: {msg}", "toast.score_range":"スコアは 0〜100 の数値である必要があります", "toast.override_set":"{name} の上書きを設定しました", "toast.reset":"{name} をリセットしました", "toast.aa_saved":"Artificial Analysis キーを保存しました", "toast.stored_removed":"保存済みキーを削除しました", "toast.remove_key_failed":"キーを削除できません: {msg}", "toast.aa_refreshed":"Artificial Analysis のスコアを更新しました", "toast.refresh_failed":"更新に失敗しました: {msg}", "toast.load_profiles_failed":"プロファイルを読み込めません: {msg}", "toast.duplicated":"{name} を複製しました", "toast.now_default":"{name} がデフォルトになりました", "toast.deleted":"{name} を削除しました", "toast.default_reassigned":" — デフォルトは auto になりました", "toast.saved_profile":"{name} を保存しました", "toast.file_too_large":"このファイルはプロファイルのエクスポートには大きすぎます。", "toast.load_integrations_failed":"統合オプションを読み込めません: {msg}", "toast.load_mi_failed":"モデルデータソースを読み込めません: {msg}", "toast.source_added":"ソースを追加しました", "toast.legacy_removed":"レガシー「__custom__」エントリを削除しました", "toast.saved_as":"{name} を {slug} として保存しました。モデルを下で取得してください。", "confirm.remove_provider":"{name} のキーを削除しますか？ {name} へのリクエストは失敗し始めます。", "confirm.remove_model":"モデル {name} を削除しますか？", "confirm.remove_custom":"プロバイダー「{name}」とそのモデルを削除しますか？", "confirm.sign_out_others":"この管理者としての他のすべてのブラウザをサインアウトしますか？", "confirm.reset_score":"{name} を AA スコアにリセットしますか？", "confirm.remove_aa_key":"保存済みの Artificial Analysis キーを削除しますか？ 環境変数のキーがあれば再び使われます。", "confirm.change_slug":"API 識別子を「{old}」から「{new}」に変更しますか？\n\nmodel: 「{old}」を送信するすべてのクライアントが動作しなくなります。", "confirm.delete_source":"このメタデータソースを削除しますか？", "confirm.legacy_remove":"レガシー「__custom__」プロバイダーキー（{prefix}）を完全に削除しますか？\n\nルーティングには使われません。まだ必要なら別の場所に保存済みか確認してください — 復元できません。", "confirm.revoke":"「{name}」を失効しますか？\n\nこのキーを使うクライアントは直ちに 401 を受け取ります。元に戻せません — 再度アクセスが必要なら新しいキーを発行してください。", "confirm.rotate":"「{name}」をローテーションしますか？\n\n同じ制限の置換キーが作成され、一度だけ表示されます。\n\nOK = 古いキーを今すぐ失効（即時切り替え）。\nキャンセル = 自分で失効するまで古いキーを維持。", "prompt.rename_key":"キー「{name}」の新しい名前:", "prompt.set_score":"{name} の手動品質スコアを設定（0-100）:", "prompt.aa_current":"現在の AA スコア: {score}", "prompt.override_note":"任意のメモ（上書きの理由）:", "auth.session_expired":"セッションの期限が切れました。もう一度サインインしてください。", "auth.enter_creds":"ユーザー名とパスワードを入力してください。", "auth.creds_required":"ユーザー名とパスワードは必須です。", "auth.pw_mismatch":"パスワードが一致しません。", "auth.paste_token":"サーバーログの使い捨てセットアップトークンを貼り付けてください。", "auth.signed_out":"サインアウトしました。", "auth.pw_match":"パスワードが一致します。", "auth.pw_mismatch_yet":"パスワードがまだ一致しません。", "auth.new_pw_mismatch":"新しいパスワードが一致しません。", "auth.fill_three":"3 つのフィールドをすべて入力してください。", "qa.connection":"Artificial Analysis 接続", "qa.test":"接続をテスト", "qa.replace":"キーを置き換え", "qa.add":"キーを追加", "qa.remove":"キーを削除", "qa.last_sync":"最終成功同期", "qa.last_error":"最新のエラー", "qa.never":"まだ同期していません", "qa.from_env":"環境変数から", "qa.saving":"保存中…", "qa.key_hint":"このサーバーで暗号化して保存され、二度と表示されません。以前のキーはこのキーが保存されるまで有効です。", "qa.daily_limit_label":"キーの1日の上限", "qa.daily_limit_hint":"Artificial Analysis のアカウントページに記載の 24 時間あたりのリクエスト数。空欄ならドキュメント記載の 100/日を使用します。", "qa.status.not_configured":"未設定", "qa.status.connected":"接続済み", "qa.status.invalid_key":"無効なキー", "qa.status.rate_limited":"上限到達", "qa.status.connection_failed":"接続失敗", "qa.status.cached":"キャッシュデータ", "pricing.legend":"価格設定", "pricing.allow_estimates":"Auto・最安・コスト上限で参考見積もりを許可", "pricing.allow_estimates_help":"既定ではオフ。確定したプロバイダー価格のみを比較し、参考見積もりしかないモデルは Auto の対象外です。オンにすると、見積もりに基づく判断にはすべてラベルが付きます。", "confirm.bulk_remove_models":"選択した {count} 個のモデル{plural}を削除しますか？それらへのピン留めリクエストは失敗します。", "nav.chat":"チャット", "tab.chat.title":"チャット", "tab.chat.sub":"デプロイ済みモデルと対話。SDK トラフィックと同じくルーティング・キャッシュ・課金の対象です。", "ui.open_chat":"チャットを開く", "ui.open_chat_hint":"ブラウザからデプロイ済みモデルとチャット。SDK トラフィックと同じルーティング・キャッシュ・コスト追計です。", "chat.new":"新規チャット", "chat.settings_title":"チャット設定", "chat.default_title":"新しいチャット", "chat.clear_history":"履歴を削除…", "chat.conversations_aria":"会話", "chat.model_aria":"モデル", "chat.regenerate":"応答を再生成", "chat.empty_title":"何でも聞いてください。", "chat.empty_sub":"リクエストはエンジン経由でルーティングされます。SDK トラフィックと同じルーティング・キャッシュ・コスト追計です。", "chat.input_placeholder":"GeekCubo にメッセージ…", "chat.send":"送信", "chat.stop":"停止", "chat.system_prompt":"システムプロンプト…", "chat.system_prompt_set":"システムプロンプト ✓", "chat.system_ph":"あなたは有能なアシスタントです…", "chat.system_help":"空欄 = チャットのデフォルトを使用。会話ごとに保存。", "chat.save_prompt":"プロンプトを保存", "chat.default_model":"デフォルトモデル", "chat.default_model_help":"新しい会話で使用。会話内の選択が優先されます。", "chat.temperature":"温度", "chat.max_tokens":"最大出力トークン", "chat.default_system_prompt":"デフォルトのシステムプロンプト", "chat.default_system_prompt_ph":"あなたは簡潔なエンジニアリングアシスタントです。", "chat.default_system_help":"独自のプロンプトを持たない会話に適用されます。", "chat.save_history":"このサーバーにチャット履歴を保存する", "chat.retention_days":"会話の保持期間（日）", "chat.retention_help":"古い会話は削除されます。空欄ですべて保持。", "chat.font_size":"メッセージの文字サイズ", "chat.fs_small":"小", "chat.fs_medium":"中", "chat.fs_large":"大", "chat.enter_to_send":"Enter キーで送信", "chat.privacy_note":"会話はこのサーバーのデータベースに保存されます。リクエストは設定したプロバイダーへ送られ、SDK トラフィックと同じ扱いです。", "chat.privacy_ack":"チャットのトラフィックが設定済みプロバイダーに送られることを理解しています", "chat.save_settings":"設定を保存", "chat.model_auto":"自動（ルーターが選択）", "chat.no_conversations":"まだ会話はありません。", "chat.delete_convo_title":"この会話を削除", "chat.kbd_enter_send":"Enter で送信 · Shift+Enter で改行", "chat.kbd_ctrl_enter_send":"Ctrl+Enter で送信 · Enter で改行", "chat.tokens_meta":"入力 {in} · 出力 {out}", "chat.error_note":"生成が完了前に停止しました。", "chat.upstream_error":"上流モデルがエラーを返しました。", "toast.chat_load_failed":"チャットデータの読み込みに失敗: {msg}", "toast.chat_failed":"チャットリクエストが失敗: {msg}", "toast.chat_convo_deleted":"会話を削除しました", "toast.chat_cleared":"{count} 件の会話を削除しました", "toast.chat_temp_range":"温度は 0〜2 の範囲で指定してください", "toast.chat_settings_saved":"チャット設定を保存しました", "toast.chat_open_convo":"先に会話を開いてください", "toast.chat_saved_prompt":"この会話のシステムプロンプトを保存しました", "confirm.delete_conversation":"この会話を削除しますか？\n\nメッセージはサーバーのデータベースから削除されます。使用量とコストの記録は分析に残ります。", "confirm.clear_chat_history":"保存済みのすべての会話を削除しますか？\n\nこのサーバーに保存されたすべてのチャットメッセージが削除されます。使用量とコストの記録は分析に残ります。", "q.ov_score":"手動スコア (0–100)", "q.ov_note":"メモ", "q.ov_model_ph":"例: openai/gpt-4o, anthropic/claude-…", "q.ov_note_ph":"AA スコアを上書きする理由", "q.ov_apply":"上書きを適用", "q.ov_clear":"上書きを解除", "q.ov_help":"1つ以上のモデルIDをカンマ区切りで指定 — 上書きは列挙したすべてのモデルに適用されます。手動スコアは常にAAスコアより優先されます。", "toast.q_ids_required":"モデルIDを1つ以上入力してください", "toast.q_too_many":"一括処理は最大500モデルIDです", "toast.q_bulk_set":"{count} 件のモデルに上書きを設定しました", "toast.q_bulk_clear":"{count} 件のモデルの上書きを解除しました", "providers.bulk_actions":"モデルの一括操作", "providers.select_all":"すべて選択", "providers.selected_count":"{count} 件選択", "providers.bulk_capability":"機能", "providers.bulk_capability_state":"機能の状態", "providers.cap_tools":"ツール", "providers.cap_vision":"画像認識", "providers.cap_supported":"対応", "providers.cap_unsupported":"非対応", "providers.cap_unknown":"不明", "providers.cap_catalog":"カタログを使用", "providers.cap_json_mode":"JSONモード", "providers.cap_json_schema":"JSONスキーマ", "providers.apply":"適用", "providers.enable":"有効化", "providers.disable":"無効化", "providers.remove_selected":"選択項目を削除", "providers.resolve_metadata":"解決", "toast.metadata_resolved":"メタデータ：解決 {resolved}、曖昧 {ambiguous}、未一致 {unmatched}、失敗 {failed}。", "select.search_ph":"カタログキーを検索…", "providers.catalog_key_ph":"カタログキーを検索…", "select.remove_item":"{name} を削除", "select.use_custom":"「{name}」を使用", "select.no_matches":"一致するモデルがありません", "select.more_results":"他 {count} 件 — 入力して絞り込み", "q.ov_model_search_ph":"モデルを検索して選択…", "q.ov_help_picker":"1 つ以上のモデルを検索して選択するか、下の表で行にチェックを入れてください。手動スコアは常に AA スコアより優先されます。", "q.filter_ph":"モデルを絞り込み…", "q.select_filtered":"絞り込み結果を選択", "q.select_all_filtered":"絞り込んだモデルをすべて選択", "q.deselect_all":"すべて選択解除", "q.bulk_set":"選択項目にスコアを設定", "q.bulk_clear":"選択した上書きを解除", "q.select_model":"{name} を選択", "confirm.q_bulk_clear":"選択した {count} 個のモデルの手動上書きを解除しますか？", "qa.daily_limit_short":"1 日の上限", "chat.attach":"ファイルを添付", "chat.attach_drop":"ファイルをドロップして添付", "chat.attach_remove":"添付を削除", "chat.attach_unreadable":"このファイルは読み取れませんでした。ファイル名のみ送信されます。", "chat.attach_uploading":"アップロード中…", "chat.attach_too_large":"大きすぎます（最大 {max} MB）", "toast.chat_attach_failed":"{name} を添付できませんでした: {msg}", "toast.chat_attach_disabled":"このサーバーでは添付が無効です。", "toast.chat_attach_too_many":"メッセージごとに最大 {max} 個の添付。", "toast.chat_attach_extract_failed":"{name}: 読み取れませんでした（{msg}）", "toast.chat_attach_wait":"アップロードの完了を待ってください。", "chat.search_toggle":"ウェブ検索", "chat.search_settings":"ウェブ検索", "chat.search_help":"有効にすると、GeekCubo は回答前にウェブを検索し、使用したページを引用します。結果はシステムメッセージとして挿入されるため、どのモデルでも利用できます。", "chat.search_mode":"検索モード", "chat.search_mode_off":"オフ", "chat.search_mode_manual":"手動（メッセージごと）", "chat.search_mode_auto":"自動（予約）", "chat.search_mode_help":"手動では入力欄に切り替えボタンが表示されます。自動は予約済みで未実装です。", "chat.search_backend":"検索バックエンド", "chat.search_backend_none":"バックエンドを選択…", "chat.search_backend_searxng":"SearXNG（セルフホスト）", "chat.search_backend_brave":"Brave 検索 API", "chat.search_backend_tavily":"Tavily", "chat.search_url":"SearXNG の URL", "chat.search_url_ph":"http://searxng:8080/", "chat.search_url_help":"SearXNG インスタンスのベース URL。インストーラーの search プロファイルが内部ネットワークで提供します。", "chat.search_api_key":"API キー", "chat.search_api_key_ph":"保存済みキーを置き換える新しいキーを貼り付け", "chat.search_key_clear":"保存済みキーを削除", "chat.search_key_help":"このサーバーに暗号化して保存され、二度と表示されません。Brave と Tavily はキーが必要で、SearXNG は不要です。", "chat.search_max_searches":"会話あたりの最大検索回数", "chat.search_max_results":"検索ごとの結果数", "chat.search_max_fetches":"検索ごとの取得ページ数", "chat.search_timeout":"検索タイムアウト（秒）", "chat.search_test":"接続をテスト", "chat.search_testing":"テスト中…", "chat.search_test_ok":"{ms} ミリ秒で {count} 件の結果", "chat.search_test_failed":"検索テストに失敗しました: {msg}", "chat.search_key_state_unset":"キー未保存", "chat.search_key_state_set":"キー保存済み", "chat.search_key_state_undecryptable":"保存済みキーを復号できません", "chat.context_budget":"コンテキスト: {tokens} / {budget} トークン", "chat.context_omitted":"以前のメッセージを {count} 件省略", "chat.sources":"出典", "chat.search_used":"ウェブ検索: {backend}", "toast.search_saved":"ウェブ検索設定を保存しました", "toast.search_save_failed":"ウェブ検索設定を保存できませんでした: {msg}", "toast.search_test_failed":"ウェブ検索のテストに失敗しました", "nav.local":"ローカル AI", "tab.local.title":"ローカル AI", "tab.local.sub":"自分のマシン上のモデルをこのルーター経由で提供します。", "local.title":"ローカル AI 接続", "local.sub":"自分のマシンで動くモデルへルーティングします。小さなコネクターがこのサーバーへ外向きに接続するため、ポートを開けたり受信トンネルを用意したりする必要はありません。", "local.refresh":"更新", "local.setup_button":"マシンをセットアップ", "local.feature_off_title":"サーバーでローカル AI 接続が無効になっています", "local.feature_off_body":"サーバーの環境で LOCAL_CONNECT_ENABLED=true を設定して再起動し、このページを再読み込みしてください。", "local.url_missing_title":"公開 URL が設定されていません", "local.url_missing_body":"コネクターが接続するアドレス（例 https://example.com）を LOCAL_CONNECT_PUBLIC_URL に設定すると、インストールコマンドとサービスファイルが自動で埋まります。", "local.settings_title":"ルーティングの動作", "local.settings_sub":"ローカルモデルを自動選択に含めるか、ローカル失敗時にクラウドへフォールバックできるかを制御します。", "local.set_enabled":"ローカルマシンをルーティングに使用する", "local.set_auto":"自動選択にローカルモデルを含める", "local.set_no_fallback":"ローカルモデル失敗時にクラウドへフォールバックしない", "local.settings_help":"ローカルモデルが自動選択の対象になるのは、価格がゼロで確定しており、マシンが承認済みかつオンラインのときだけです。「フォールバックしない」を有効にすると、ローカルのみのリクエストはクラウドで処理されず失敗します。", "local.save_settings":"保存", "local.settings_saved":"ローカルルーティング設定を保存しました。", "local.machines_title":"マシン", "local.machines_sub":"各マシンは 1 つのコネクターです。保留中のマシンは表示されますが、承認するまでトラフィックは送られません。", "local.machines_empty":"まだマシンがありません。「マシンをセットアップ」で登録コードを生成してください。", "local.enrollments_title":"登録コード", "local.enrollments_sub":"コネクターを登録するための使い捨てコードです。マシンが初めて接続したときに消費されます。", "local.new_code":"新しいコード", "local.install_title":"コネクターをインストール", "local.install_sub":"モデルをホストするマシンで実行します（Ollama、LM Studio、vLLM、llama.cpp、または [OI] 互換サーバー）。", "local.service_files":"サービスとして実行", "local.delete":"削除", "local.never":"なし", "local.ctx_suffix":"コンテキスト", "local.ctx_unknown":"コンテキスト不明", "local.no_models":"このマシンはまだモデルを報告していません。", "local.no_enrollments":"登録コードはありません。", "local.enroll_active":"有効", "local.enroll_used":"使用済み", "local.status_online":"オンライン", "local.status_offline":"オフライン", "local.status_pending":"承認待ち", "local.status_approved":"承認済み", "local.status_revoked":"取り消し済み", "local.pending_note":"このマシンは承認待ちです。モデルは一覧に出ますが、トラフィックは送られません。", "local.action_approve":"承認", "local.action_discover":"モデルを検出", "local.action_revoke":"取り消す", "local.action_rotate":"認証情報を更新", "local.action_delete":"削除", "local.meta_host":"ホスト名", "local.meta_platform":"プラットフォーム", "local.meta_agent":"コネクターのバージョン", "local.meta_adapters":"アダプター", "local.meta_seen":"最終確認", "local.col_model":"モデル", "local.col_adapter":"アダプター種別", "local.col_context":"コンテキスト", "local.col_caps":"機能", "local.col_enabled":"有効", "local.kpi_machines":"マシン", "local.kpi_online":"現在オンライン", "local.kpi_pending":"承認待ち", "local.kpi_models":"モデル", "local.toast_approved":"マシンを承認しました。", "local.toast_revoked":"マシンを取り消しました。", "local.toast_deleted":"マシンを削除しました。", "local.toast_discovered":"モデル一覧を更新しました。", "local.confirm_revoke":"このマシンを取り消しますか？コネクターは即座に切断され、認証情報を更新するまで再接続できません。", "local.confirm_delete_machine":"このマシンとモデル一覧を削除しますか？この操作は元に戻せません。", "local.confirm_rotate":"このマシンの認証情報を更新しますか？稼働中のコネクターは再接続するまで動作し、その後は古い認証情報が拒否されます。", "local.confirm_delete_enrollment":"この登録コードを削除しますか？", "local.credential_once_title":"新しい認証情報を今すぐコピーしてください", "local.credential_once_body":"表示されるのは一度だけです。マシン上のコネクター設定に保存してください。", "local.wizard_title":"ローカルマシンを接続", "local.wizard_close":"閉じる", "local.wizard_back":"戻る", "local.wizard_next":"次へ", "local.wizard_done":"完了", "local.step1":"有効化", "local.step2":"登録コード", "local.step3":"インストール", "local.step4":"登録", "local.step5":"起動", "local.step6":"承認", "local.step7":"モデル", "local.step8":"自動ルーティング", "local.w0_title":"機能を有効にします", "local.w0_body":"ローカル AI 接続はサーバー側の機能です。コネクターが登録できるように、事前に有効化する必要があります。", "local.w0_ready":"機能は有効です。登録コードの作成に進んでください。", "local.w0_blocked":"このサーバーでは機能が無効です。LOCAL_CONNECT_ENABLED=true を設定して再起動し、このページを再読み込みしてください。", "local.w1_title":"登録コードを作成します", "local.w1_body":"使い捨てコードは 1 つのコネクターに登録を許可します。短時間で有効期限が切れます。", "local.w1_name":"マシン名（任意）", "local.w1_name_ph":"例: office-gpu", "local.w1_name_help":"一覧でこのマシンを識別するラベルです。後から変更できます。", "local.w1_created":"登録コードを作成しました", "local.w2_title":"コネクターパッケージをインストールします", "local.w2_body":"モデルをホストするマシンにコネクターをインストールします。Python 3.11 以降が必要です。", "local.w2_note":"システムパッケージから分離するため、仮想環境にインストールしてください。", "local.w3_title":"マシンを登録します", "local.w3_body":"手順 2 のコードを使って登録コマンドを実行します。認証情報はコネクターの設定ファイルに書き込まれます。", "local.w3_note":"コードは 1 回限りです。期限切れの場合は新しく作成してください。", "local.w4_title":"コネクターを起動します", "local.w4_body":"まず前面でコネクターを実行して接続を確認し、その後サービスに移してください。", "local.w4_note":"コネクターは外向きの WebSocket を 1 本維持し、自動的に再接続します。", "local.w5_title":"マシンが表示されるのを待ちます", "local.w5_body":"コネクターが接続すると、マシンがここに表示されます。少し時間がかかる場合は更新してください。", "local.w5_seen":"{name} が接続しました。", "local.w5_waiting":"まだマシンが接続していません。", "local.w5_recheck":"再確認", "local.w6_title":"マシンを承認します", "local.w6_body":"新しいマシンは管理者が承認するまで保留のままです。それまでは何もルーティングされません。", "local.w6_none":"承認できるマシンがまだありません。", "local.w6_must_approve":"続行する前に保留中のマシンを承認してください。", "local.w7_title":"自動選択でローカルモデルを有効にします", "local.w7_body":"「自動選択にローカルモデルを含める」をオンにし、ルーティングしたいモデルを有効にします。ローカルモデルが自動選択されるのは、価格がゼロで確定している場合だけです。", "local.w7_done":"セットアップが完了しました。ローカルモデルはプロバイダーとルーティングのページに表示されます。" },
  de: { "q.tabs_label":"Qualitätsbereiche", "q.tab_models":"Modelle", "q.tab_scores":"Qualitätswerte", "q.tab_aa":"Artificial-Analysis-Verbindung", "q.col_availability":"Verfügbarkeit", "q.avail_yes":"verfügbar", "q.avail_no":"kein Anbieterschlüssel", "q.avail_no_title":"Kein konfigurierter Anbieterschlüssel bedient dieses Modell. Benchmark-Daten allein machen ein Modell nicht einsetzbar.", "q.sync_title":"Benchmark-Synchronisierung", "q.sync_last_ok":"Letzte erfolgreiche Synchronisierung", "q.sync_last_attempt":"Letzter Versuch", "q.sync_returned":"Von AA gelieferte Modelle", "q.sync_matched":"Im Katalog zugeordnet", "q.sync_unmatched":"Nicht zugeordnet", "q.sync_overrides":"Manuelle Werte", "q.sync_outcome_ok":"erfolgreich", "q.sync_outcome_failed":"fehlgeschlagen", "q.sync_need_key":"Fügen Sie auf dem Tab Artificial Analysis einen Schlüssel hinzu, um Benchmark-Werte zu synchronisieren. Manuelle Werte funktionieren ohne Schlüssel.", "q.sync_never":"Mit diesem Schlüssel wurde noch nicht synchronisiert. Nutzen Sie „Von AA aktualisieren“.", "q.sync_no_models":"Die letzte Synchronisierung lieferte keine Modelle.", "q.status_line":"{matched} Modelle mit Benchmark-Daten · {overrides} manuelle Werte", "q.src.live":"aktuell", "q.src.stale_cache":"zwischengespeichert (AA nicht erreichbar)", "q.src.stale_db":"zwischengespeichert (gespeicherter Stand)", "q.src.error":"Synchronisierung fehlgeschlagen", "q.src.missing_key":"kein API-Schlüssel", "q.auto_status":"Status des Auto-Routings", "q.auto_status_hint":"Was model=\"auto\" gerade wählen würde. Hängt von den konfigurierten Anbietern ab, nicht von der Benchmark-Synchronisierung.", "q.auto_no_provider":"Kein einsetzbares Modell erfüllt die aktuellen Anforderungen. Fügen Sie auf der Seite Anbieter einen Schlüssel hinzu. Das ist unabhängig von der Artificial-Analysis-Synchronisierung.", "qa.credential":"API-Schlüssel", "qa.cred_stored":"Auf diesem Server gespeichert (verschlüsselt)", "qa.cred_env":"Aus der Serverumgebung", "qa.last_test":"Letzter Verbindungstest", "qa.last_test_ok":"Letzter erfolgreicher Test", "qa.not_tested":"Noch nicht getestet", "qa.sync_status":"Benchmark-Abgleich", "qa.tier":"Tarif {tier}", "qa.troubleshooting":"Fehlerbehebung bei der Verbindung", "qa.status.key_configured":"Schlüssel hinterlegt", "qa.sync.not_configured":"Nicht eingerichtet", "qa.sync.never_synced":"Noch nie synchronisiert", "qa.sync.synced":"Synchronisiert", "qa.sync.sync_failed":"Synchronisierung fehlgeschlagen", "qa.err.invalid_key":"Ungültiger Schlüssel", "qa.err.insufficient_tier":"Tarif enthält diesen Endpunkt nicht", "qa.err.endpoint_retired":"Endpunkt eingestellt", "qa.err.rate_limited":"Anfragelimit erreicht", "qa.err.timeout":"Zeitüberschreitung", "qa.err.malformed_response":"Unerwartete Antwort", "qa.err.no_data":"Keine Modelle geliefert", "qa.err.no_catalog_match":"Keine Katalogtreffer", "qa.err.server_error":"AA-Serverfehler", "qa.err.connection_failed":"Verbindung fehlgeschlagen", "auth.tagline":"Ein Gateway. Jedes KI-Modell.", "auth.welcome":"Willkommen zurück", "auth.subtitle":"Melden Sie sich bei der Administratorkonsole dieser GeekCubo-Installation an.", "auth.api_key":"API-Schlüssel", "auth.continue":"Weiter", "nav.search":"Suchen", "nav.overview":"Übersicht", "nav.providers":"Anbieter", "nav.routing":"Weiterleitung", "nav.analytics":"Analysen", "nav.api_keys":"API-Schlüssel", "nav.help_docs":"Hilfe & Doku", "nav.sign_out":"Abmelden", "status.connected":"Verbunden", "status.disconnected":"Getrennt", "auth.checking":"Prüfe…", "auth.welcome_aboard":"Willkommen an Bord.", "auth.key_invalid":"Dieser Schlüssel funktioniert nicht. Prüfen Sie das Präfix sk-geek-…", "tab.overview.title":"Übersicht", "tab.overview.sub":"Ihr Single-Tenant-LLM-Router auf einen Blick.", "tab.providers.title":"Anbieterschlüssel", "tab.providers.sub":"BYOK — im Ruhezustand verschlüsselt, für Upstream-LLM-Aufrufe genutzt.", "tab.routing.title":"Routing", "tab.routing.sub":"Wie model='auto' für jede Anfrage das richtige Modell auswählt.", "tab.analytics.title":"Analysen", "tab.analytics.sub":"Nur lokale Ausgaben, Latenz und Anfrageverlauf.", "tab.keys.title":"API-Schlüssel", "tab.keys.sub":"sk-geek-* Schlüssel für SDK- und CLI-Inferenzverkehr.", "nav.quality":"Qualität", "tab.quality.title":"Qualitätswerte", "tab.quality.sub":"Echte Benchmark-Werte für die Qualitätsstrategie. Stammen von Artificial Analysis.", "auth.username":"Benutzername", "auth.password":"Passwort", "auth.sign_in":"Anmelden", "nav.security":"Sicherheit", "tab.security.title":"Sicherheit", "tab.security.sub":"Administratorkonto, Passwort und Sitzungen.", "tab.profiles.title":"Routing-Profile", "tab.profiles.sub":"Benannte Auto-Konfigurationen, die Clients über die Modell-ID auswählen.", "tab.integrations.title":"Tool verbinden", "tab.integrations.sub":"Fertige Konfiguration für OpenCode, Claude Code, Cursor und weitere.", "tab.intelligence.title":"Modelldaten", "tab.intelligence.sub":"Woher Preise und Limits der Modelle stammen.", "auth.loading":"Wird geladen…", "auth.checking_status":"Administratorstatus wird geprüft.", "auth.signin_title":"Anmelden", "auth.signin_sub":"Administratorzugang zu dieser GeekCubo-Installation.", "auth.forgot":"Passwort vergessen?", "auth.reset_hint":"Setzen Sie es auf dem Host oder im Container zurück:", "auth.reset_note":"Schlüssel, Anbieter und Nutzung bleiben unverändert.", "auth.setup_title":"Administratorkonto erstellen", "auth.setup_sub":"Verwaltet diese GeekCubo-Installation: Anbieter-Zugangsdaten, API-Schlüssel und Routing.", "auth.min_password":"Mindestens 8 Zeichen", "auth.confirm_password":"Passwort bestätigen", "auth.setup_token":"Setup-Token", "auth.from_log":"Aus dem Server-Log", "auth.create_admin":"Administrator erstellen", "auth.where_token":"Wo ist das Setup-Token?", "auth.token_hint":"Wird beim ersten Start im Server-Log ausgegeben. Um ein neues auszustellen:", "auth.toggle_password":"Passwort anzeigen oder verbergen", "ov.spend":"Ausgaben (7 T.)", "ov.savings":"Routing-Ersparnis", "ov.p50":"p50-Latenz", "ov.models":"Einsetzbare Modelle", "ov.quickstart":"Schnellstart", "ov.recent":"Letzte Aktivität", "prov.title":"Anbieterschlüssel", "prov.tab_std":"Standardanbieter", "prov.tab_custom":"Eigene Anbieter", "routing.strategy":"Routing-Strategie", "routing.pools":"Modell-Pools", "routing.advanced":"Fallback, Eskalation & Kontinuität", "routing.explain":"Routing-Entscheidung testen", "profiles.title":"Routing-Profile", "int.title":"KI-Tool verbinden", "md.title":"Modelldatenquellen", "md.lookup":"Preisabfrage", "an.spend":"Ausgaben nach Modell", "an.latency":"Latenz nach Anbieter", "an.recent":"Letzte Anfragen", "keys.title":"Router-API-Schlüssel", "sec.sessions":"Sitzungen", "q.setup":"Qualitätsbewertung einrichten", "q.models":"Modelle", "preset.heading":"Mit einer Vorlage starten", "preset.sub":"Vorlagen öffnen den Editor vorbefüllt — vor dem Speichern alles anpassbar.", "preset.economy":"Das günstigste geeignete Modell pro Anfrage. Geringste Kosten, keine Qualitätsgrenze.", "preset.premium":"Stärkste Modelle zuerst, Preis egal. Für Arbeit, bei der Qualität zählt.", "preset.coding":"Tool-Aufrufe und lange Prompts gehen in den Hard-Pool. Für Agenten- und Editor-Arbeit.", "preset.fast":"Ausgewogenes Routing, das geringere Latenz im Pool bevorzugt.", "ui.profiles":"Profile", "ui.security":"Sicherheit", "ui.api_keys":"API-Schlüssel", "ui.connect_a_tool":"Tool verbinden", "ui.model_data":"Modelldaten", "ui.connecting":"Verbinde…", "ui.language":"Sprache", "ui.light":"Hell", "ui.system":"System", "ui.dark":"Dunkel", "ui.openai_compatible_base_url":"OpenAI-kompatible Basis-URL", "ui.copy":"Kopieren", "ui.use_this_in_any_openai_compatible_client":"In jedem OpenAI-kompatiblen Client verwenden.", "ui.signed_in":"Angemeldet", "ui.security_and_sessions":"Sicherheit & Sitzungen", "ui.api_keys_2":"API-Schlüssel", "ui.sign_out":"Abmelden", "ui.you_re_up_point_any_openai_sdk_at_your_b":"Alles bereit — richten Sie jedes OpenAI-SDK auf Ihre Basis-URL.", "ui.last_5_requests_routed_through_this_serv":"Letzte 5 über diesen Server geleitete Anfragen.", "ui.view_all":"Alle ansehen", "ui.no_requests_yet":"Noch keine Anfragen.", "ui.new_here_get_fully_set_up_in_2_minutes":"Neu hier? In 2 Minuten vollständig eingerichtet", "ui.re_enter_as_a_named_provider":"Als benannten Anbieter neu eingeben", "ui.remove_legacy_entry":"Altbestand entfernen", "ui.provider":"Anbieter", "ui.others_openai_format":"Andere (OpenAI-Format)", "ui.api_key":"API-Schlüssel", "ui.provider_name":"Anbietername", "ui.display_name_a_unique_internal_slug_is_d":"Anzeigename. Ein eindeutiger interner Slug wird automatisch abgeleitet.", "ui.api_base_url":"API-Basis-URL", "ui.usually_ends_in_v1_must_be_https_unless_":"Endet meist auf /v1. Muss https sein, außer der Host steht in CUSTOM_PROVIDER_ALLOWED_LOCAL_HOSTS.", "ui.api_key_2":"API-Schlüssel", "ui.encrypted_at_rest_never_displayed_again_":"Im Ruhezustand verschlüsselt. Wird nach dem Speichern nie wieder angezeigt.", "ui.prefix":"Präfix", "ui.status":"Status", "ui.no_provider_keys_yet":"Noch keine Anbieterschlüssel", "ui.add_at_least_one_to_start_routing_real_t":"Fügen Sie mindestens einen hinzu, um echten Verkehr zu leiten. Anbieter oben wählen oder Schnellauswahl anklicken.", "ui.lowest_cost_that_clears_your_quality_flo":"Die günstigste Option, die Ihre Qualitätsgrenze erfüllt. Sichere Vorgabe bei beliebig vielen Anbietern.", "ui.recommended":"Empfohlen", "ui.lowest_per_token_cost_meeting_the_reques":"Geringste Kosten pro Token, die die Anforderungen der Anfrage erfüllen. Ausgabequalität kann variieren.", "ui.highest_score_from_artificial_analysis_o":"Höchster Wert aus Artificial Analysis oder Ihren manuellen Überschreibungen. Ohne Werte wird der Preis als Näherung genutzt.", "ui.re_ranks_by_observed_success_rate_and_la":"Sortiert nach beobachteter Erfolgsrate und Latenz neu, sobald ein Modell hier 20+ Anfragen hat. Bis dahin: Ausgewogen.", "ui.sends_each_request_to_your_mundane_or_ha":"Leitet jede Anfrage anhand beobachtbarer Signale (Tools, Größe, Länge) in den Mundane- oder Hard-Pool.", "ui.highest_throughput_and_lowest_first_toke":"Höchster Durchsatz und geringste Erst-Token-Latenz aus Benchmark-Daten. Aus Kompatibilitätsgründen beibehalten.", "ui.legacy":"Altbestand", "ui.registered_models":"Registrierte Modelle", "ui.show":"Anzeigen", "ui.deployable":"Einsetzbar", "ui.custom_providers":"Eigene Anbieter", "ui.model":"Modell", "ui.capabilities":"Fähigkeiten", "ui.context":"Kontext", "ui.price_1m_in_out":"Preis /1M (Ein · Aus)", "ui.availability":"Verfügbarkeit", "ui.pools":"Pools", "ui.previous":"Zurück", "ui.next":"Weiter", "ui.fallback_and_escalation_always_keep_the_":"Fallback und Eskalation behalten stets die geforderten Fähigkeiten der Anfrage bei. Entscheidungen fallen vor dem Start; Modelle wechseln nie mitten im Stream.", "ui.maximum_attempts_primary_fallbacks":"Maximale Versuche (primär + Fallbacks)", "ui.what_counts_as_retryable":"Was als wiederholbar gilt", "ui.quality_floor_percentile_0_off":"Qualitätsgrenze (Perzentil, 0 = aus)", "ui.needs_quality_scores_ignored_and_reporte":"Benötigt Qualitätswerte; wird ignoriert (und gemeldet), wenn keine vorliegen.", "ui.what_the_quality_floor_does":"Was die Qualitätsgrenze bewirkt", "ui.balanced_weighs_price_against_quality_th":"Ausgewogen wägt Preis gegen Qualität. Die Grenze schließt Modelle unterhalb dieses Perzentils aus, damit ein sehr günstiges, aber schwaches Modell nicht gewinnen kann. Auf 0 setzen, um sie ganz abzuschalten.", "ui.messages":"Nachrichten ≥", "ui.prompt_characters":"Prompt-Zeichen ≥", "ui.how_request_signals_are_measured":"Wie Anfragesignale gemessen werden", "ui.mode":"Modus", "ui.off":"Aus", "ui.manual_client_sends_x_geek_escalate":"Manuell (Client sendet x-geek-escalate)", "ui.auto_after_repeated_upstream_failures":"Automatisch (nach wiederholten Upstream-Fehlern)", "ui.failures_before_escalating":"Fehler vor Eskalation", "ui.max_escalations_per_conversation":"Max. Eskalationen pro Unterhaltung", "ui.destination_pool":"Ziel-Pool", "ui.when_escalation_triggers":"Wann Eskalation ausgelöst wird", "ui.remember_for_minutes":"Merken für (Minuten)", "ui.what_continuity_does":"Was Kontinuität bewirkt", "ui.save_routing_policy":"Routing-Richtlinie speichern", "ui.dry_run_shows_which_model_auto_would_cho":"Probelauf: zeigt, welches Modell Auto wählen würde und warum. Es wird nichts an den Anbieter gesendet.", "ui.messages_2":"Nachrichten", "ui.prompt_chars":"Prompt-Zeichen", "ui.explain":"Erklären", "ui.three_filters_applied_in_order":"Drei Filter, der Reihe nach angewendet.", "ui.how_each_strategy_maps_to_litellm_router":"Wie jede Strategie auf den LiteLLM Router abgebildet wird", "ui.strategy":"Strategie", "ui.import_json":"JSON importieren", "ui.new_profile":"Neues Profil", "ui.generates_configuration_that_points_a_cl":"Erzeugt eine Konfiguration, die einen Client auf dieses GeekCubo zeigt. Schlüssel werden per Umgebungsvariable referenziert, nie eingebettet.", "ui.search_tools":"Tools suchen", "ui.routing_profile_or_model":"Routing-Profil oder Modell", "ui.endpoint":"Endpunkt", "ui.format":"Format", "ui.download":"Herunterladen", "ui.add_source":"Quelle hinzufügen", "ui.name":"Name", "ui.https_url_models_dev_compatible_json":"HTTPS-URL (models.dev-kompatibles JSON)", "ui.save_source":"Quelle speichern", "ui.cancel":"Abbrechen", "ui.shows_what_each_enabled_source_reports_f":"Zeigt, was jede aktive Quelle für ein Modell meldet und welchen Wert GeekCubo nutzen würde. Ihre eigenen Preise gewinnen immer.", "ui.look_up":"Nachschlagen", "ui.routing":"Routing", "ui.volume":"Volumen", "ui.routing_decisions":"Routing-Entscheidungen", "ui.how_auto_requests_were_classified_and_wh":"Wie Auto-Anfragen eingestuft wurden und wohin sie gingen.", "ui.by_tier":"Nach Tier", "ui.by_strategy":"Nach Strategie", "ui.by_routing_id":"Nach Routing-ID", "ui.top_models_served":"Meistgenutzte Modelle", "ui.reliability":"Zuverlässigkeit", "ui.errors_by_cause":"Fehler nach Ursache", "ui.compare_against_a_baseline_model":"Mit einem Basismodell vergleichen", "ui.none":"Keine", "ui.compare":"Vergleichen", "ui.how_the_comparison_is_calculated":"Wie der Vergleich berechnet wird", "ui.p50_and_p99_sourced_from_local_request_l":"p50 und p99 — aus lokalen Anfrage-Logs.", "ui.requests":"Anfragen", "ui.newest_first_click_a_row_to_copy_its_tra":"Neueste zuerst. Zeile anklicken, um die Trace-ID zu kopieren.", "ui.when":"Wann", "ui.tokens_in_out":"Token (Ein / Aus)", "ui.latency":"Latenz", "ui.no_traffic_yet":"Noch kein Verkehr", "ui.once_you_start_sending_requests_they_ll_":"Sobald Anfragen eingehen, erscheinen sie hier in Echtzeit.", "ui.expires":"Läuft ab", "ui.never":"Nie", "ui.7_days":"7 Tage", "ui.30_days":"30 Tage", "ui.90_days":"90 Tage", "ui.1_year":"1 Jahr", "ui.use_it_with_opencode":"Mit OpenCode verwenden:", "ui.created":"Erstellt", "ui.last_used":"Zuletzt genutzt", "ui.actions":"Aktionen", "ui.no_api_keys":"Keine API-Schlüssel", "ui.generate_one_above_to_start_sending_requ":"Erzeugen Sie oben einen, um Anfragen per SDK oder CLI zu senden.", "ui.administrator":"Administrator", "ui.the_single_local_account_that_controls_t":"Das einzige lokale Konto, das diese Installation steuert.", "ui.password_was_reset_from_the_command_line":"Passwort wurde über die Kommandozeile zurückgesetzt", "ui.change_password":"Passwort ändern", "ui.current_password":"Aktuelles Passwort", "ui.new_password":"Neues Passwort", "ui.confirm_new_password":"Neues Passwort bestätigen", "ui.update_password":"Passwort aktualisieren", "ui.signed_in_browsers_for_this_administrato":"Angemeldete Browser dieses Administrators. Sitzungen laufen nach 12 Stunden ab, oder nach 60 Minuten Inaktivität.", "ui.log_out_all_other_sessions":"Alle anderen Sitzungen abmelden", "ui.device":"Gerät", "ui.last_active":"Zuletzt aktiv", "ui.local_recovery":"Lokale Wiederherstellung", "ui.password_recovery_is_local_only_by_desig":"Die Passwortwiederherstellung ist bewusst nur lokal — es gibt keinen E-Mail-Reset und keinen öffentlichen Endpunkt, der das Passwort ändern könnte.", "ui.open_a_shell_where_geekcubo_runs_host_or":"Öffnen Sie eine Shell, in der GeekCubo läuft (Host oder Container).", "ui.choose_a_new_password_at_the_prompt_all_":"Wählen Sie an der Eingabeaufforderung ein neues Passwort. Alle Dashboard-Sitzungen werden abgemeldet; API-Schlüssel, Anbieter und Nutzungsdaten bleiben unberührt.", "ui.artificial_analysis_api_key":"Artificial Analysis API-Schlüssel", "ui.optional":"(optional)", "ui.save_key":"Schlüssel speichern", "ui.remove_stored_key":"Gespeicherten Schlüssel entfernen", "ui.how_quality_scoring_works":"Wie die Qualitätsbewertung funktioniert", "ui.paste_it_above_and_save_it_is_encrypted_":"Oben einfügen und speichern. Er wird verschlüsselt gespeichert, und bereits Cache-Inhalte werden verworfen, damit der nächste Abruf den neuen Schlüssel nutzt.", "ui.quality_scores":"Qualitätswerte", "ui.where_these_numbers_come_from":"Woher diese Zahlen kommen", "ui.manual":"Manuell", "ui.effective":"Effektiv", "ui.m_blended":"$/M kombiniert", "ui.help_and_docs":"Hilfe & Doku", "ui.what_is_geekcubo":"Was ist GeekCubo?", "ui.60_second_quickstart":"60-Sekunden-Schnellstart", "ui.keyboard_shortcuts":"Tastenkürzel", "ui.switch_tabs":"Tab wechseln", "ui.command_palette":"Befehlspalette", "ui.toggle_this_help":"Diese Hilfe ein-/ausblenden", "ui.close_drawers_palette":"Drawer / Palette schließen", "ui.going_further":"Weiter", "js.ov_empty_a":"Noch keine Anfragen.", "js.ov_empty_b":"Sobald Sie den ersten Aufruf senden, erscheint er hier.", "js.ra_unavailable":"Routing-Analysen nicht verfügbar.", "js.no_spend":"In diesem Zeitraum wurden noch keine Ausgaben erfasst.", "js.no_traffic":"Noch kein Verkehr", "toast.copied":"In die Zwischenablage kopiert", "toast.copy_blocked":"Kopieren nicht möglich — der Browser hat es blockiert", "toast.signed_in":"Angemeldet als {name}", "toast.admin_created":"Administrator {name} erstellt", "toast.signed_out":"Abgemeldet", "toast.load_providers_failed":"Anbieter konnten nicht geladen werden: {msg}", "toast.removed_provider":"{name} entfernt", "toast.api_key_empty":"Der API-Schlüssel darf nicht leer sein", "toast.saved_provider":"Schlüssel für {name} gespeichert", "toast.load_custom_failed":"Eigene Anbieter konnten nicht geladen werden: {msg}", "toast.updated":"{name} aktualisiert", "toast.model_id_empty":"Die Modell-ID darf nicht leer sein", "toast.model_id_dup":"Diese Modell-ID ist bereits registriert", "toast.model_saved":"Modell gespeichert", "toast.select_one_model":"Wählen Sie mindestens ein neues Modell", "toast.added_models_one":"1 Modell hinzugefügt", "toast.added_models_many":"{count} Modelle hinzugefügt", "toast.load_routing_failed":"Routing konnte nicht geladen werden: {msg}", "toast.routing_strategy":"Routing-Strategie: {name}", "toast.policy_saved":"Routing-Richtlinie gespeichert", "toast.load_models_failed":"Modelle konnten nicht geladen werden: {msg}", "toast.load_analytics_failed":"Analysen konnten nicht geladen werden: {msg}", "toast.load_keys_failed":"Schlüssel konnten nicht geladen werden: {msg}", "toast.revoked":"{name} widerrufen", "toast.name_empty":"Der Name darf nicht leer sein", "toast.key_renamed":"Schlüssel umbenannt", "toast.name_first":"Geben Sie dem Schlüssel zuerst einen Namen", "toast.created":"{name} erstellt", "toast.load_security_failed":"Sicherheitseinstellungen konnten nicht geladen werden: {msg}", "toast.password_updated":"Passwort aktualisiert — andere Geräte wurden abgemeldet", "toast.load_quality_failed":"Qualitätswerte konnten nicht geladen werden: {msg}", "toast.score_range":"Der Wert muss eine Zahl zwischen 0 und 100 sein", "toast.override_set":"Überschreibung für {name} gesetzt", "toast.reset":"{name} zurückgesetzt", "toast.aa_saved":"Artificial-Analysis-Schlüssel gespeichert", "toast.stored_removed":"Gespeicherten Schlüssel entfernt", "toast.remove_key_failed":"Schlüssel konnte nicht entfernt werden: {msg}", "toast.aa_refreshed":"Werte von Artificial Analysis aktualisiert", "toast.refresh_failed":"Aktualisierung fehlgeschlagen: {msg}", "toast.load_profiles_failed":"Profile konnten nicht geladen werden: {msg}", "toast.duplicated":"{name} dupliziert", "toast.now_default":"{name} ist jetzt der Standard", "toast.deleted":"{name} gelöscht", "toast.default_reassigned":" — Standard ist jetzt auto", "toast.saved_profile":"{name} gespeichert", "toast.file_too_large":"Diese Datei ist zu groß für einen Profil-Export.", "toast.load_integrations_failed":"Integrationsoptionen konnten nicht geladen werden: {msg}", "toast.load_mi_failed":"Modelldatenquellen konnten nicht geladen werden: {msg}", "toast.source_added":"Quelle hinzugefügt", "toast.legacy_removed":"Legacy-Eintrag \"__custom__\" entfernt", "toast.saved_as":"{name} als {slug} gespeichert. Rufen Sie die Modelle unten ab.", "confirm.remove_provider":"Den Schlüssel von {name} entfernen? Anfragen an {name} schlagen dann fehl.", "confirm.remove_model":"Modell {name} entfernen?", "confirm.remove_custom":"Anbieter \"{name}\" und seine Modelle entfernen?", "confirm.sign_out_others":"Alle anderen Browser dieses Administrators abmelden?", "confirm.reset_score":"{name} auf den AA-Wert zurücksetzen?", "confirm.remove_aa_key":"Den gespeicherten Artificial-Analysis-Schlüssel entfernen? Ein Umgebungsschlüssel übernimmt dann wieder.", "confirm.change_slug":"Die API-Kennung von \"{old}\" in \"{new}\" ändern?\n\nJeder Client, der model: \"{old}\" sendet, funktioniert nicht mehr.", "confirm.delete_source":"Diese Metadatenquelle löschen?", "confirm.legacy_remove":"Den Legacy-Anbieterschlüssel \"__custom__\" ({prefix}) dauerhaft entfernen?\n\nEr wird nicht für das Routing genutzt. Stellen Sie sicher, dass Sie den Schlüssel andernorts gespeichert haben — er kann nicht wiederhergestellt werden.", "confirm.revoke":"\"{name}\" widerrufen?\n\nClients mit diesem Schlüssel erhalten sofort 401. Das lässt sich nicht rückgängig machen — geben Sie einen neuen Schlüssel aus, wenn Sie wieder Zugriff brauchen.", "confirm.rotate":"\"{name}\" rotieren?\n\nEin Ersatzschlüssel mit denselben Einschränkungen wird erstellt und einmal angezeigt.\n\nOK = alten Schlüssel jetzt widerrufen (sofortiger Wechsel).\nAbbrechen = alten Schlüssel behalten, bis Sie ihn selbst widerrufen.", "prompt.rename_key":"Schlüssel \"{name}\" umbenennen in:", "prompt.set_score":"Manuellen Qualitätswert für {name} festlegen (0-100):", "prompt.aa_current":"Der AA-Wert ist derzeit: {score}", "prompt.override_note":"Optionale Notiz (warum überschreiben Sie?):", "auth.session_expired":"Ihre Sitzung ist abgelaufen. Melden Sie sich erneut an.", "auth.enter_creds":"Geben Sie Benutzername und Passwort ein.", "auth.creds_required":"Benutzername und Passwort sind erforderlich.", "auth.pw_mismatch":"Die Passwörter stimmen nicht überein.", "auth.paste_token":"Fügen Sie das einmalige Setup-Token aus dem Server-Log ein.", "auth.signed_out":"Abgemeldet.", "auth.pw_match":"Die Passwörter stimmen überein.", "auth.pw_mismatch_yet":"Die Passwörter stimmen noch nicht überein.", "auth.new_pw_mismatch":"Die neuen Passwörter stimmen nicht überein.", "auth.fill_three":"Füllen Sie alle drei Felder aus.", "qa.connection":"Artificial-Analysis-Verbindung", "qa.test":"Verbindung testen", "qa.replace":"Schlüssel ersetzen", "qa.add":"Schlüssel hinzufügen", "qa.remove":"Schlüssel entfernen", "qa.last_sync":"Letzte erfolgreiche Synchronisierung", "qa.last_error":"Letzter Fehler", "qa.never":"noch nie synchronisiert", "qa.from_env":"aus der Umgebung", "qa.saving":"Wird gespeichert…", "qa.key_hint":"Wird auf diesem Server verschlüsselt und nie wieder angezeigt. Der vorherige Schlüssel bleibt aktiv, bis dieser gespeichert ist.", "qa.daily_limit_label":"Tageslimit des Schlüssels", "qa.daily_limit_hint":"Anfragen pro 24 Stunden, wie auf Ihrer Artificial-Analysis-Kontoseite angegeben. Leer lassen für das dokumentierte Limit von 100/Tag.", "qa.status.not_configured":"Nicht konfiguriert", "qa.status.connected":"Verbunden", "qa.status.invalid_key":"Ungültiger Schlüssel", "qa.status.rate_limited":"Limit erreicht", "qa.status.connection_failed":"Verbindung fehlgeschlagen", "qa.status.cached":"Gecachte Daten", "pricing.legend":"Preise", "pricing.allow_estimates":"Referenzschätzungen in Auto, Günstigste und Kostenobergrenzen zulassen", "pricing.allow_estimates_help":"Standardmäßig aus. Nur bestätigte Anbieterpreise werden verglichen; Modelle mit nur einer Referenzschätzung bleiben aus Auto heraus. Wenn aktiviert, wird jede schätzungsbasierte Entscheidung gekennzeichnet.", "confirm.bulk_remove_models":"{count} ausgewählte Modelle entfernen? Pinning-Anfragen an diese schlagen fehl.", "nav.chat":"Chats", "tab.chat.title":"Chats", "tab.chat.sub":"Mit Ihren bereitgestellten Modellen sprechen. Routing, Cache und Kosten wie SDK-Traffic.", "ui.open_chat":"Chat öffnen", "ui.open_chat_hint":"Chatten Sie im Browser mit Ihren bereitgestellten Modellen — dasselbe Routing, derselbe Cache und dieselbe Kostenverfolgung wie SDK-Traffic.", "chat.new":"Neuer Chat", "chat.settings_title":"Chat-Einstellungen", "chat.default_title":"Neuer Chat", "chat.clear_history":"Verlauf löschen …", "chat.conversations_aria":"Unterhaltungen", "chat.model_aria":"Modell", "chat.regenerate":"Antwort neu generieren", "chat.empty_title":"Fragen Sie alles.", "chat.empty_sub":"Anfragen laufen über die Engine — dasselbe Routing, derselbe Cache und dieselbe Kostenverfolgung wie SDK-Traffic.", "chat.input_placeholder":"Nachricht an GeekCubo …", "chat.send":"Senden", "chat.stop":"Stopp", "chat.system_prompt":"System-Prompt …", "chat.system_prompt_set":"System-Prompt ✓", "chat.system_ph":"Du bist ein hilfreicher Assistent …", "chat.system_help":"Leer = Chat-Standard verwenden. Pro Unterhaltung gespeichert.", "chat.save_prompt":"Prompt speichern", "chat.default_model":"Standardmodell", "chat.default_model_help":"Für neue Unterhaltungen. Die Auswahl in der Unterhaltung überschreibt sie.", "chat.temperature":"Temperatur", "chat.max_tokens":"Max. Ausgabe-Tokens", "chat.default_system_prompt":"Standard-System-Prompt", "chat.default_system_prompt_ph":"Du bist ein präziser Engineering-Assistent.", "chat.default_system_help":"Gilt für Unterhaltungen ohne eigenen Prompt.", "chat.save_history":"Chat-Verlauf auf diesem Server speichern", "chat.retention_days":"Unterhaltungen aufbewahren (Tage)", "chat.retention_help":"Ältere Unterhaltungen werden entfernt. Leer = alles behalten.", "chat.font_size":"Textgröße der Nachrichten", "chat.fs_small":"Klein", "chat.fs_medium":"Mittel", "chat.fs_large":"Groß", "chat.enter_to_send":"Enter sendet die Nachricht", "chat.privacy_note":"Unterhaltungen bleiben in der Datenbank dieses Servers. Anfragen gehen an die von Ihnen konfigurierten Anbieter — genau wie SDK-Traffic.", "chat.privacy_ack":"Ich verstehe, dass Chat-Traffic an die konfigurierten Anbieter geht", "chat.save_settings":"Einstellungen speichern", "chat.model_auto":"Auto (Router wählt)", "chat.no_conversations":"Noch keine Unterhaltungen.", "chat.delete_convo_title":"Diese Unterhaltung löschen", "chat.kbd_enter_send":"Enter = senden · Shift+Enter = neue Zeile", "chat.kbd_ctrl_enter_send":"Ctrl+Enter = senden · Enter = neue Zeile", "chat.tokens_meta":"{in} rein · {out} raus", "chat.error_note":"Die Generierung wurde vor Abschluss gestoppt.", "chat.upstream_error":"Das Upstream-Modell hat einen Fehler gemeldet.", "toast.chat_load_failed":"Chat-Daten konnten nicht geladen werden: {msg}", "toast.chat_failed":"Chat-Anfrage fehlgeschlagen: {msg}", "toast.chat_convo_deleted":"Unterhaltung gelöscht", "toast.chat_cleared":"{count} Unterhaltungen gelöscht", "toast.chat_temp_range":"Temperature muss zwischen 0 und 2 liegen", "toast.chat_settings_saved":"Chat-Einstellungen gespeichert", "toast.chat_open_convo":"Öffnen Sie zuerst eine Unterhaltung", "toast.chat_saved_prompt":"System-Prompt für diese Unterhaltung gespeichert", "confirm.delete_conversation":"Diese Unterhaltung löschen?\n\nNachrichten werden aus der Datenbank des Servers entfernt. Nutzungs- und Kostenaufzeichnungen bleiben in der Analyse.", "confirm.clear_chat_history":"ALLE gespeicherten Unterhaltungen löschen?\n\nAlle auf diesem Server gespeicherten Chat-Nachrichten werden entfernt. Nutzungs- und Kostenaufzeichnungen bleiben in der Analyse.", "q.ov_score":"Manuelle Punktzahl (0–100)", "q.ov_note":"Notiz", "q.ov_model_ph":"z. B. openai/gpt-4o, anthropic/claude-…", "q.ov_note_ph":"Warum diese AA-Punktzahl überschrieben wird", "q.ov_apply":"Override anwenden", "q.ov_clear":"Override entfernen", "q.ov_help":"Eine oder mehrere Modell-IDs, kommagetrennt — der Override gilt für jedes aufgeführte Modell. Manuelle Punktzahlen schlagen AA-Punktzahlen immer.", "toast.q_ids_required":"Gib mindestens eine Modell-ID ein", "toast.q_too_many":"Der Bulk-Vorgang ist auf 500 Modell-IDs begrenzt", "toast.q_bulk_set":"Override für {count} Modell(e) gesetzt", "toast.q_bulk_clear":"Overrides für {count} Modell(e) entfernt", "providers.bulk_actions":"Massenaktionen für Modelle", "providers.select_all":"Alle auswählen", "providers.selected_count":"{count} ausgewählt", "providers.bulk_capability":"Fähigkeit", "providers.bulk_capability_state":"Fähigkeitsstatus", "providers.cap_tools":"Werkzeuge", "providers.cap_vision":"Bildverarbeitung", "providers.cap_supported":"Unterstützt", "providers.cap_unsupported":"Nicht unterstützt", "providers.cap_unknown":"Unbekannt", "providers.cap_catalog":"Katalog verwenden", "providers.cap_json_mode":"JSON-Modus", "providers.cap_json_schema":"JSON-Schema", "providers.apply":"Anwenden", "providers.enable":"Aktivieren", "providers.disable":"Deaktivieren", "providers.remove_selected":"Auswahl entfernen", "providers.resolve_metadata":"Abgleichen", "toast.metadata_resolved":"Metadaten: {resolved} zugeordnet, {ambiguous} mehrdeutig, {unmatched} ohne Treffer, {failed} fehlgeschlagen.", "select.search_ph":"Katalogschlüssel suchen…", "providers.catalog_key_ph":"Katalogschlüssel suchen…", "select.remove_item":"{name} entfernen", "select.use_custom":"„{name}“ verwenden", "select.no_matches":"Keine passenden Modelle", "select.more_results":"{count} weitere – weiter tippen zum Eingrenzen", "q.ov_model_search_ph":"Modelle suchen und auswählen…", "q.ov_help_picker":"Suchen und wählen Sie ein oder mehrere Modelle oder markieren Sie Zeilen in der Tabelle unten. Manuelle Punktzahlen haben immer Vorrang vor AA-Werten.", "q.filter_ph":"Modelle filtern…", "q.select_filtered":"Gefilterte auswählen", "q.select_all_filtered":"Alle gefilterten Modelle auswählen", "q.deselect_all":"Auswahl aufheben", "q.bulk_set":"Punktzahl für Auswahl setzen", "q.bulk_clear":"Ausgewählte Overrides löschen", "q.select_model":"{name} auswählen", "confirm.q_bulk_clear":"Manuelle Overrides für {count} ausgewählte Modelle löschen?", "qa.daily_limit_short":"Tageslimit", "chat.attach":"Dateien anhängen", "chat.attach_drop":"Dateien zum Anhängen ablegen", "chat.attach_remove":"Anhang entfernen", "chat.attach_unreadable":"Diese Datei konnte nicht gelesen werden; nur ihr Name wird gesendet.", "chat.attach_uploading":"Wird hochgeladen…", "chat.attach_too_large":"Zu groß (max. {max} MB)", "toast.chat_attach_failed":"{name} konnte nicht angehängt werden: {msg}", "toast.chat_attach_disabled":"Anhänge sind auf diesem Server deaktiviert.", "toast.chat_attach_too_many":"Höchstens {max} Anhänge pro Nachricht.", "toast.chat_attach_extract_failed":"{name}: konnte nicht gelesen werden ({msg})", "toast.chat_attach_wait":"Warte, bis die Uploads abgeschlossen sind.", "chat.search_toggle":"Websuche", "chat.search_settings":"Websuche", "chat.search_help":"Wenn aktiv, durchsucht GeekCubo vor der Antwort das Web und zitiert die verwendeten Seiten. Ergebnisse werden als Systemnachricht eingefügt, daher kann jedes Modell sie nutzen.", "chat.search_mode":"Suchmodus", "chat.search_mode_off":"Aus", "chat.search_mode_manual":"Manuell (pro Nachricht)", "chat.search_mode_auto":"Automatisch (reserviert)", "chat.search_mode_help":"Manuell zeigt einen Schalter im Eingabefeld. Automatisch ist reserviert und noch nicht umgesetzt.", "chat.search_backend":"Suchdienst", "chat.search_backend_none":"Dienst wählen…", "chat.search_backend_searxng":"SearXNG (selbst gehostet)", "chat.search_backend_brave":"Brave-Suche-API", "chat.search_backend_tavily":"Tavily", "chat.search_url":"SearXNG-URL", "chat.search_url_ph":"http://searxng:8080/", "chat.search_url_help":"Basis-URL Ihrer SearXNG-Instanz. Das search-Profil des Installers stellt sie im internen Netz bereit.", "chat.search_api_key":"API-Schlüssel", "chat.search_api_key_ph":"Neuen Schlüssel einfügen, um den gespeicherten zu ersetzen", "chat.search_key_clear":"Gespeicherten Schlüssel entfernen", "chat.search_key_help":"Verschlüsselt auf diesem Server gespeichert und nie wieder angezeigt. Brave und Tavily benötigen einen Schlüssel; SearXNG nicht.", "chat.search_max_searches":"Max. Suchen pro Unterhaltung", "chat.search_max_results":"Ergebnisse pro Suche", "chat.search_max_fetches":"Seiten pro Suche", "chat.search_timeout":"Such-Timeout (Sekunden)", "chat.search_test":"Verbindung testen", "chat.search_testing":"Teste…", "chat.search_test_ok":"{count} Ergebnisse in {ms} ms", "chat.search_test_failed":"Suchtest fehlgeschlagen: {msg}", "chat.search_key_state_unset":"Kein Schlüssel gespeichert", "chat.search_key_state_set":"Schlüssel gespeichert", "chat.search_key_state_undecryptable":"Gespeicherter Schlüssel lässt sich nicht entschlüsseln", "chat.context_budget":"Kontext: {tokens} / {budget} Token", "chat.context_omitted":"{count} frühere Nachrichten ausgelassen", "chat.sources":"Quellen", "chat.search_used":"Websuche: {backend}", "toast.search_saved":"Websuche-Einstellungen gespeichert", "toast.search_save_failed":"Websuche-Einstellungen konnten nicht gespeichert werden: {msg}", "toast.search_test_failed":"Websuche-Test fehlgeschlagen", "nav.local":"Lokale KI", "tab.local.title":"Lokale KI", "tab.local.sub":"Modelle von Ihren eigenen Rechnern über diesen Router bereitstellen.", "local.title":"Lokale KI verbinden", "local.sub":"Leiten Sie Anfragen an Modelle auf Ihren eigenen Rechnern weiter. Ein kleiner Connector wählt sich bei diesem Server ein, daher werden keine Ports geöffnet und kein eingehender Tunnel benötigt.", "local.refresh":"Aktualisieren", "local.setup_button":"Rechner einrichten", "local.feature_off_title":"Lokale KI ist auf dem Server deaktiviert", "local.feature_off_body":"Setzen Sie LOCAL_CONNECT_ENABLED=true in der Serverumgebung und starten Sie neu, dann laden Sie diese Seite erneut.", "local.url_missing_title":"Keine öffentliche URL konfiguriert", "local.url_missing_body":"Setzen Sie LOCAL_CONNECT_PUBLIC_URL auf die Adresse, die Connectoren anwählen sollen (zum Beispiel https://example.com), damit Installationsbefehl und Dienstdateien ausgefüllt werden.", "local.settings_title":"Routing-Verhalten", "local.settings_sub":"Legt fest, ob lokale Modelle an Auto teilnehmen und ob eine Anfrage auf die Cloud zurückfallen darf.", "local.set_enabled":"Lokale Rechner für das Routing zulassen", "local.set_auto":"Lokale Modelle in die automatische Auswahl einbeziehen", "local.set_no_fallback":"Bei Ausfall eines lokalen Modells niemals auf die Cloud zurückfallen", "local.settings_help":"Lokale Modelle werden nur dann für Auto berücksichtigt, wenn ihr Preis bestätigt null ist und der Rechner genehmigt und online ist. Mit aktivem \"niemals zurückfallen\" schlägt eine rein lokale Anfrage fehl, statt von einem Cloud-Anbieter bedient zu werden.", "local.save_settings":"Speichern", "local.settings_saved":"Lokale Routing-Einstellungen gespeichert.", "local.machines_title":"Rechner", "local.machines_sub":"Jeder Rechner ist ein Connector. Ausstehende Rechner sind sichtbar, erhalten aber erst nach der Genehmigung Verkehr.", "local.machines_empty":"Noch keine Rechner. Verwenden Sie \"Rechner einrichten\", um einen Registrierungscode zu erzeugen.", "local.enrollments_title":"Registrierungscodes", "local.enrollments_sub":"Einmalige Codes, mit denen sich ein Connector registriert. Jeder Code wird beim ersten Verbinden eines Rechners verbraucht.", "local.new_code":"Neuer Code", "local.install_title":"Connector installieren", "local.install_sub":"Führen Sie dies auf dem Rechner aus, der Ihre Modelle hostet (Ollama, LM Studio, vLLM, llama.cpp oder ein beliebiger [OI]-kompatibler Server).", "local.service_files":"Als Dienst ausführen", "local.delete":"Löschen", "local.never":"nie", "local.ctx_suffix":"Kontext", "local.ctx_unknown":"Kontext unbekannt", "local.no_models":"Dieser Rechner hat noch keine Modelle gemeldet.", "local.no_enrollments":"Keine Registrierungscodes.", "local.enroll_active":"Aktiv", "local.enroll_used":"Verwendet", "local.status_online":"Verbunden", "local.status_offline":"Nicht verbunden", "local.status_pending":"Genehmigung ausstehend", "local.status_approved":"Genehmigt", "local.status_revoked":"Widerrufen", "local.pending_note":"Dieser Rechner wartet auf Genehmigung. Modelle werden gelistet, erhalten aber keinen Verkehr.", "local.action_approve":"Genehmigen", "local.action_discover":"Modelle ermitteln", "local.action_revoke":"Widerrufen", "local.action_rotate":"Anmeldedaten erneuern", "local.action_delete":"Löschen", "local.meta_host":"Rechnername", "local.meta_platform":"Plattform", "local.meta_agent":"Connector-Version", "local.meta_adapters":"Adapter", "local.meta_seen":"Zuletzt gesehen", "local.col_model":"Modell", "local.col_adapter":"Adaptertyp", "local.col_context":"Kontext", "local.col_caps":"Fähigkeiten", "local.col_enabled":"Aktiviert", "local.kpi_machines":"Rechner", "local.kpi_online":"Jetzt verbunden", "local.kpi_pending":"Genehmigung ausstehend", "local.kpi_models":"Modelle", "local.toast_approved":"Rechner genehmigt.", "local.toast_revoked":"Rechner widerrufen.", "local.toast_deleted":"Rechner gelöscht.", "local.toast_discovered":"Modellliste aktualisiert.", "local.confirm_revoke":"Diesen Rechner widerrufen? Der Connector wird sofort getrennt und kann sich erst wieder verbinden, wenn Sie die Anmeldedaten erneuern.", "local.confirm_delete_machine":"Diesen Rechner und seine Modellliste löschen? Dies kann nicht rückgängig gemacht werden.", "local.confirm_rotate":"Anmeldedaten dieses Rechners erneuern? Der laufende Connector arbeitet bis zum erneuten Verbinden weiter, danach werden die alten Anmeldedaten abgelehnt.", "local.confirm_delete_enrollment":"Diesen Registrierungscode löschen?", "local.credential_once_title":"Kopieren Sie die neuen Anmeldedaten jetzt", "local.credential_once_body":"Sie werden nur einmal angezeigt. Speichern Sie sie in der Connector-Konfiguration auf dem Rechner.", "local.wizard_title":"Lokalen Rechner verbinden", "local.wizard_close":"Schließen", "local.wizard_back":"Zurück", "local.wizard_next":"Weiter", "local.wizard_done":"Fertig", "local.step1":"Aktivieren", "local.step2":"Registrierungscode", "local.step3":"Installieren", "local.step4":"Registrieren", "local.step5":"Starten", "local.step6":"Genehmigen", "local.step7":"Modelle", "local.step8":"Auto-Routing", "local.w0_title":"Funktion einschalten", "local.w0_body":"Lokale KI ist eine serverseitige Funktion. Sie muss aktiviert sein, bevor sich Connectoren registrieren können.", "local.w0_ready":"Die Funktion ist aktiviert. Fahren Sie fort, um einen Registrierungscode zu erstellen.", "local.w0_blocked":"Die Funktion ist auf diesem Server deaktiviert. Setzen Sie LOCAL_CONNECT_ENABLED=true, starten Sie neu und laden Sie diese Seite erneut.", "local.w1_title":"Registrierungscode erstellen", "local.w1_body":"Ein einmaliger Code berechtigt genau einen Connector zur Registrierung. Er läuft nach kurzer Zeit ab.", "local.w1_name":"Rechnername (optional)", "local.w1_name_ph":"z. B. buero-gpu", "local.w1_name_help":"Eine Bezeichnung, um diesen Rechner in der Liste wiederzuerkennen. Sie können ihn später umbenennen.", "local.w1_created":"Registrierungscode erstellt", "local.w2_title":"Connector-Paket installieren", "local.w2_body":"Installieren Sie den Connector auf dem Rechner, der Ihre Modelle hostet. Python 3.11 oder neuer ist erforderlich.", "local.w2_note":"Installieren Sie ihn in einer virtuellen Umgebung, um ihn von Systempaketen getrennt zu halten.", "local.w3_title":"Rechner registrieren", "local.w3_body":"Führen Sie den Registrierungsbefehl mit dem Code aus Schritt 2 aus. Die Anmeldedaten werden in die Connector-Konfigurationsdatei geschrieben.", "local.w3_note":"Der Code ist einmalig. Ist er abgelaufen, erstellen Sie einen neuen.", "local.w4_title":"Connector starten", "local.w4_body":"Führen Sie den Connector im Vordergrund aus, um die Verbindung zu beobachten, und überführen Sie ihn dann in einen Dienst.", "local.w4_note":"Der Connector hält eine ausgehende WebSocket-Verbindung offen und verbindet sich automatisch neu.", "local.w5_title":"Warten, bis der Rechner erscheint", "local.w5_body":"Sobald der Connector verbunden ist, erscheint der Rechner hier. Aktualisieren Sie, falls es einen Moment dauert.", "local.w5_seen":"{name} ist verbunden.", "local.w5_waiting":"Es hat sich noch kein Rechner verbunden.", "local.w5_recheck":"Erneut prüfen", "local.w6_title":"Rechner genehmigen", "local.w6_body":"Ein neuer Rechner bleibt ausstehend, bis ein Administrator ihn genehmigt. Bis dahin wird nichts dorthin geleitet.", "local.w6_none":"Es gibt noch keinen Rechner zum Genehmigen.", "local.w6_must_approve":"Genehmigen Sie den ausstehenden Rechner, bevor Sie fortfahren.", "local.w7_title":"Lokale Modelle in Auto aktivieren", "local.w7_body":"Aktivieren Sie \"Lokale Modelle in die automatische Auswahl einbeziehen\" und schalten Sie die gewünschten Modelle ein. Lokale Modelle werden nur dann für Auto gewählt, wenn ihr Preis bestätigt null ist.", "local.w7_done":"Die Einrichtung ist abgeschlossen. Lokale Modelle erscheinen jetzt auf den Seiten Anbieter und Routing." },
  fr: { "q.tabs_label":"Sections qualité", "q.tab_models":"Modèles", "q.tab_scores":"Scores de qualité", "q.tab_aa":"Connexion Artificial Analysis", "q.col_availability":"Disponibilité", "q.avail_yes":"disponible", "q.avail_no":"aucune clé fournisseur", "q.avail_no_title":"Aucune clé fournisseur configurée ne sert ce modèle. Des données de benchmark ne rendent pas un modèle déployable.", "q.sync_title":"Synchronisation des benchmarks", "q.sync_last_ok":"Dernière synchronisation réussie", "q.sync_last_attempt":"Dernière tentative", "q.sync_returned":"Modèles renvoyés par AA", "q.sync_matched":"Associés au catalogue", "q.sync_unmatched":"Non associés", "q.sync_overrides":"Scores manuels", "q.sync_outcome_ok":"réussie", "q.sync_outcome_failed":"échouée", "q.sync_need_key":"Ajoutez une clé dans l'onglet Artificial Analysis pour synchroniser les scores. Les scores manuels fonctionnent sans clé.", "q.sync_never":"Aucune synchronisation n'a encore eu lieu avec cette clé. Utilisez Actualiser depuis AA.", "q.sync_no_models":"La dernière synchronisation n'a renvoyé aucun modèle.", "q.status_line":"{matched} modèles avec données de benchmark · {overrides} scores manuels", "q.src.live":"à jour", "q.src.stale_cache":"en cache (AA injoignable)", "q.src.stale_db":"en cache (instantané enregistré)", "q.src.error":"échec de synchronisation", "q.src.missing_key":"aucune clé API", "q.auto_status":"État du routage automatique", "q.auto_status_hint":"Ce que model=\"auto\" choisirait maintenant. Dépend des fournisseurs configurés, pas de la synchronisation des benchmarks.", "q.auto_no_provider":"Aucun modèle déployable ne répond aux exigences actuelles. Ajoutez une clé sur la page Fournisseurs. Cela n'a rien à voir avec la synchronisation Artificial Analysis.", "qa.credential":"Clé API", "qa.cred_stored":"Stockée sur ce serveur (chiffrée)", "qa.cred_env":"Depuis l'environnement du serveur", "qa.last_test":"Dernier test de connexion", "qa.last_test_ok":"Dernier test réussi", "qa.not_tested":"Pas encore testée", "qa.sync_status":"Synchronisation", "qa.tier":"offre {tier}", "qa.troubleshooting":"Dépannage de la connexion", "qa.status.key_configured":"Clé enregistrée", "qa.sync.not_configured":"Non configuré", "qa.sync.never_synced":"Jamais synchronisé", "qa.sync.synced":"Synchronisé", "qa.sync.sync_failed":"Échec de synchronisation", "qa.err.invalid_key":"Clé invalide", "qa.err.insufficient_tier":"Offre sans accès à ce point d'accès", "qa.err.endpoint_retired":"Point d'accès retiré", "qa.err.rate_limited":"Limite de requêtes atteinte", "qa.err.timeout":"Délai dépassé", "qa.err.malformed_response":"Réponse inattendue", "qa.err.no_data":"Aucun modèle renvoyé", "qa.err.no_catalog_match":"Aucune correspondance au catalogue", "qa.err.server_error":"Erreur du serveur AA", "qa.err.connection_failed":"Échec de connexion", "auth.tagline":"Une passerelle. Tous les modèles d'IA.", "auth.welcome":"Bon retour", "auth.subtitle":"Connectez-vous à la console d'administration de cette installation GeekCubo.", "auth.api_key":"Clé API", "auth.continue":"Continuer", "nav.search":"Rechercher", "nav.overview":"Vue d'ensemble", "nav.providers":"Fournisseurs", "nav.routing":"Routage IA", "nav.analytics":"Analytique", "nav.api_keys":"Clés API", "nav.help_docs":"Aide et docs", "nav.sign_out":"Se déconnecter", "status.connected":"Connecté", "status.disconnected":"Déconnecté", "auth.checking":"Vérification…", "auth.welcome_aboard":"Bienvenue.", "auth.key_invalid":"Cette clé n'a pas fonctionné. Vérifiez le préfixe sk-geek-…", "tab.overview.title":"Vue d'ensemble", "tab.overview.sub":"Votre routeur LLM mono-locataire en un coup d'œil.", "tab.providers.title":"Clés fournisseur", "tab.providers.sub":"BYOK — chiffrées au repos, utilisées pour appeler les LLM amont.", "tab.routing.title":"Routage", "tab.routing.sub":"Comment model='auto' choisit le bon modèle pour chaque requête.", "tab.analytics.title":"Analytique", "tab.analytics.sub":"Dépenses, latence et historique des requêtes en local uniquement.", "tab.keys.title":"Clés API", "tab.keys.sub":"Clés sk-geek-* qui authentifient le trafic d'inférence SDK et CLI.", "nav.quality":"Qualité", "tab.quality.title":"Scores de qualité", "tab.quality.sub":"Scores de référence réels pour la stratégie de routage par qualité. Provenant d'Artificial Analysis.", "auth.username":"Nom d'utilisateur", "auth.password":"Mot de passe", "auth.sign_in":"Se connecter", "nav.security":"Sécurité", "tab.security.title":"Sécurité", "tab.security.sub":"Compte administrateur, mot de passe et sessions.", "tab.profiles.title":"Profils de routage", "tab.profiles.sub":"Configurations Auto nommées que les clients choisissent par identifiant de modèle.", "tab.integrations.title":"Connecter un outil", "tab.integrations.sub":"Configuration prête à l'emploi pour OpenCode, Claude Code, Cursor et plus.", "tab.intelligence.title":"Données des modèles", "tab.intelligence.sub":"D'où viennent les prix et les limites des modèles.", "auth.loading":"Chargement…", "auth.checking_status":"Vérification de l'état de l'administrateur.", "auth.signin_title":"Se connecter", "auth.signin_sub":"Accès administrateur à cette installation de GeekCubo.", "auth.forgot":"Mot de passe oublié ?", "auth.reset_hint":"Réinitialisez-le sur l'hôte ou le conteneur :", "auth.reset_note":"Les clés, les fournisseurs et l’usage ne sont pas affectés.", "auth.setup_title":"Créer un compte administrateur", "auth.setup_sub":"Contrôle cette installation de GeekCubo : identifiants des fournisseurs, clés API et routage.", "auth.min_password":"8 caractères minimum", "auth.confirm_password":"Confirmer le mot de passe", "auth.setup_token":"Jeton d'installation", "auth.from_log":"Depuis le journal du serveur", "auth.create_admin":"Créer l’administrateur", "auth.where_token":"Où se trouve le jeton d'installation ?", "auth.token_hint":"Affiché dans le journal du serveur au premier démarrage. Pour en émettre un nouveau :", "auth.toggle_password":"Afficher ou masquer le mot de passe", "ov.spend":"Dépenses (7 j)", "ov.savings":"Économies de routage", "ov.p50":"latence p50", "ov.models":"Modèles déployables", "ov.quickstart":"Démarrage rapide", "ov.recent":"Activité récente", "prov.title":"Clés fournisseur", "prov.tab_std":"Fournisseurs standard", "prov.tab_custom":"Fournisseurs personnalisés", "routing.strategy":"Stratégie de routage", "routing.pools":"Pools de modèles", "routing.advanced":"Repli, escalade et continuité", "routing.explain":"Tester une décision de routage", "profiles.title":"Profils de routage", "int.title":"Connecter votre outil IA", "md.title":"Sources de données des modèles", "md.lookup":"Recherche de prix", "an.spend":"Dépenses par modèle", "an.latency":"Latence par fournisseur", "an.recent":"Requêtes récentes", "keys.title":"Clés API du routeur", "sec.sessions":"Sessions", "q.setup":"Configurer le score de qualité", "q.models":"Modèles", "preset.heading":"Partir d’un modèle", "preset.sub":"Les modèles ouvrent l’éditeur prérempli — ajustez tout avant d’enregistrer.", "preset.economy":"Le modèle compétent le moins cher pour chaque requête. Dépense minimale, sans plancher de qualité.", "preset.premium":"Les modèles les plus puissants d’abord, prix ignoré. Pour un travail où la qualité prime.", "preset.coding":"Les appels d’outils et les longs prompts vont au pool Hard. Pour les agents et éditeurs.", "preset.fast":"Routage équilibré privilégiant une latence plus faible dans le pool.", "ui.profiles":"Profils", "ui.security":"Sécurité", "ui.api_keys":"Clés API", "ui.connect_a_tool":"Connecter un outil", "ui.model_data":"Données des modèles", "ui.connecting":"Connexion…", "ui.language":"Langue", "ui.light":"Clair", "ui.system":"Système", "ui.dark":"Sombre", "ui.openai_compatible_base_url":"URL de base compatible OpenAI", "ui.copy":"Copier", "ui.use_this_in_any_openai_compatible_client":"À utiliser dans tout client compatible OpenAI.", "ui.signed_in":"Connecté", "ui.security_and_sessions":"Sécurité et sessions", "ui.api_keys_2":"Clés API", "ui.sign_out":"Se déconnecter", "ui.you_re_up_point_any_openai_sdk_at_your_b":"Tout est prêt : pointez n'importe quel SDK OpenAI vers votre URL de base.", "ui.last_5_requests_routed_through_this_serv":"5 dernières requêtes routées par ce serveur.", "ui.view_all":"Tout voir", "ui.no_requests_yet":"Aucune requête pour l'instant.", "ui.new_here_get_fully_set_up_in_2_minutes":"Nouveau ? Configuration complète en 2 minutes", "ui.re_enter_as_a_named_provider":"Ressaisir comme fournisseur nommé", "ui.remove_legacy_entry":"Supprimer l'entrée héritée", "ui.provider":"Fournisseur", "ui.others_openai_format":"Autres (format OpenAI)", "ui.api_key":"Clé API", "ui.provider_name":"Nom du fournisseur", "ui.display_name_a_unique_internal_slug_is_d":"Nom affiché. Un slug interne unique en est dérivé automatiquement.", "ui.api_base_url":"URL de base de l'API", "ui.usually_ends_in_v1_must_be_https_unless_":"Se termine généralement par /v1. Doit être en https sauf si l'hôte figure dans CUSTOM_PROVIDER_ALLOWED_LOCAL_HOSTS.", "ui.api_key_2":"Clé API", "ui.encrypted_at_rest_never_displayed_again_":"Chiffrée au repos. Jamais réaffichée après enregistrement.", "ui.prefix":"Préfixe", "ui.status":"État", "ui.no_provider_keys_yet":"Aucune clé fournisseur pour l'instant", "ui.add_at_least_one_to_start_routing_real_t":"Ajoutez-en au moins une pour router du trafic réel. Choisissez un fournisseur ci-dessus ou cliquez une suggestion rapide.", "ui.lowest_cost_that_clears_your_quality_flo":"Le coût le plus bas qui dépasse votre seuil de qualité. Choix sûr quel que soit le nombre de fournisseurs.", "ui.recommended":"Recommandé", "ui.lowest_per_token_cost_meeting_the_reques":"Le coût par token le plus bas respectant les capacités de la requête. La qualité de sortie peut varier.", "ui.highest_score_from_artificial_analysis_o":"Le meilleur score d'Artificial Analysis ou de vos remplacements manuels. Sans scores, le prix sert d'approximation.", "ui.re_ranks_by_observed_success_rate_and_la":"Réordonne selon le taux de réussite et la latence observés dès qu'un modèle atteint 20+ requêtes ici. D'ici là : Équilibré.", "ui.sends_each_request_to_your_mundane_or_ha":"Envoie chaque requête vers votre pool Mundane ou Hard selon des signaux observables (outils, taille, longueur).", "ui.highest_throughput_and_lowest_first_toke":"Débit le plus élevé et latence du premier token la plus faible selon les benchmarks. Conservé pour compatibilité.", "ui.legacy":"Hérité", "ui.registered_models":"Modèles enregistrés", "ui.show":"Afficher", "ui.deployable":"Déployables", "ui.custom_providers":"Fournisseurs personnalisés", "ui.model":"Modèle", "ui.capabilities":"Capacités", "ui.context":"Contexte", "ui.price_1m_in_out":"Prix /1M (entrée · sortie)", "ui.availability":"Disponibilité", "ui.pools":"Pools", "ui.previous":"Précédent", "ui.next":"Suivant", "ui.fallback_and_escalation_always_keep_the_":"Le repli et l'escalade préservent toujours les capacités requises par la requête. Les décisions sont prises avant le démarrage ; les modèles ne changent jamais en cours de flux.", "ui.maximum_attempts_primary_fallbacks":"Tentatives maximales (principale + replis)", "ui.what_counts_as_retryable":"Ce qui est considéré comme réessayable", "ui.quality_floor_percentile_0_off":"Seuil de qualité (centile, 0 = désactivé)", "ui.needs_quality_scores_ignored_and_reporte":"Nécessite des scores de qualité ; ignoré (et signalé) s'il n'y en a aucun.", "ui.what_the_quality_floor_does":"Ce que fait le seuil de qualité", "ui.balanced_weighs_price_against_quality_th":"Équilibré pèse le prix et la qualité. Le seuil exclut les modèles sous ce centile, donc un modèle très bon marché mais faible ne peut pas gagner. Mettez 0 pour le désactiver entièrement.", "ui.messages":"Messages ≥", "ui.prompt_characters":"Caractères du prompt ≥", "ui.how_request_signals_are_measured":"Comment les signaux de requête sont mesurés", "ui.mode":"Mode", "ui.off":"Désactivé", "ui.manual_client_sends_x_geek_escalate":"Manuel (le client envoie x-geek-escalate)", "ui.auto_after_repeated_upstream_failures":"Automatique (après des échecs répétés du fournisseur)", "ui.failures_before_escalating":"Échecs avant escalade", "ui.max_escalations_per_conversation":"Escalades max par conversation", "ui.destination_pool":"Pool de destination", "ui.when_escalation_triggers":"Quand l'escalade se déclenche", "ui.remember_for_minutes":"Mémoriser pendant (minutes)", "ui.what_continuity_does":"Ce que fait la continuité", "ui.save_routing_policy":"Enregistrer la politique de routage", "ui.dry_run_shows_which_model_auto_would_cho":"Simulation : montre quel modèle Auto choisirait et pourquoi. Rien n'est envoyé au fournisseur.", "ui.messages_2":"Messages", "ui.prompt_chars":"Caractères du prompt", "ui.explain":"Expliquer", "ui.three_filters_applied_in_order":"Trois filtres, appliqués dans l'ordre.", "ui.how_each_strategy_maps_to_litellm_router":"Comment chaque stratégie se traduit dans LiteLLM Router", "ui.strategy":"Stratégie", "ui.import_json":"Importer du JSON", "ui.new_profile":"Nouveau profil", "ui.generates_configuration_that_points_a_cl":"Génère une configuration qui pointe un client vers ce GeekCubo. Les clés sont référencées par variable d'environnement, jamais intégrées.", "ui.search_tools":"Rechercher des outils", "ui.routing_profile_or_model":"Profil de routage ou modèle", "ui.endpoint":"Point de terminaison", "ui.format":"Format", "ui.download":"Télécharger", "ui.add_source":"Ajouter une source", "ui.name":"Nom", "ui.https_url_models_dev_compatible_json":"URL HTTPS (JSON compatible models.dev)", "ui.save_source":"Enregistrer la source", "ui.cancel":"Annuler", "ui.shows_what_each_enabled_source_reports_f":"Montre ce que chaque source active rapporte pour un modèle et quelle valeur GeekCubo utiliserait. Vos prix configurés gagnent toujours.", "ui.look_up":"Rechercher", "ui.routing":"Routage", "ui.volume":"Volume", "ui.routing_decisions":"Décisions de routage", "ui.how_auto_requests_were_classified_and_wh":"Comment les requêtes Auto ont été classées et où elles sont allées.", "ui.by_tier":"Par palier", "ui.by_strategy":"Par stratégie", "ui.by_routing_id":"Par id de routage", "ui.top_models_served":"Modèles les plus servis", "ui.reliability":"Fiabilité", "ui.errors_by_cause":"Erreurs par cause", "ui.compare_against_a_baseline_model":"Comparer à un modèle de référence", "ui.none":"Aucun", "ui.compare":"Comparer", "ui.how_the_comparison_is_calculated":"Comment la comparaison est calculée", "ui.p50_and_p99_sourced_from_local_request_l":"p50 et p99 — issues des journaux locaux de requêtes.", "ui.requests":"Requêtes", "ui.newest_first_click_a_row_to_copy_its_tra":"Plus récentes d'abord. Cliquez une ligne pour copier son trace ID.", "ui.when":"Quand", "ui.tokens_in_out":"Tokens (entrée / sortie)", "ui.latency":"Latence", "ui.no_traffic_yet":"Pas encore de trafic", "ui.once_you_start_sending_requests_they_ll_":"Dès que vous enverrez des requêtes, elles apparaîtront ici en temps réel.", "ui.expires":"Expire", "ui.never":"Jamais", "ui.7_days":"7 jours", "ui.30_days":"30 jours", "ui.90_days":"90 jours", "ui.1_year":"1 an", "ui.use_it_with_opencode":"À utiliser avec OpenCode :", "ui.created":"Créée", "ui.last_used":"Dernière utilisation", "ui.actions":"Actions", "ui.no_api_keys":"Aucune clé API", "ui.generate_one_above_to_start_sending_requ":"Générez-en une ci-dessus pour envoyer des requêtes depuis un SDK ou la CLI.", "ui.administrator":"Administrateur", "ui.the_single_local_account_that_controls_t":"Le seul compte local qui contrôle cette installation.", "ui.password_was_reset_from_the_command_line":"Le mot de passe a été réinitialisé en ligne de commande", "ui.change_password":"Changer le mot de passe", "ui.current_password":"Mot de passe actuel", "ui.new_password":"Nouveau mot de passe", "ui.confirm_new_password":"Confirmer le nouveau mot de passe", "ui.update_password":"Mettre à jour le mot de passe", "ui.signed_in_browsers_for_this_administrato":"Navigateurs connectés pour cet administrateur. Les sessions expirent après 12 heures, ou 60 minutes d'inactivité.", "ui.log_out_all_other_sessions":"Déconnecter toutes les autres sessions", "ui.device":"Appareil", "ui.last_active":"Dernière activité", "ui.local_recovery":"Récupération locale", "ui.password_recovery_is_local_only_by_desig":"La récupération du mot de passe est volontairement locale — pas de réinitialisation par e-mail, aucun point de terminaison public ne peut le changer.", "ui.open_a_shell_where_geekcubo_runs_host_or":"Ouvrez un shell où GeekCubo s'exécute (hôte ou conteneur).", "ui.choose_a_new_password_at_the_prompt_all_":"Choisissez un nouveau mot de passe à l'invite. Toutes les sessions du tableau de bord sont déconnectées ; clés API, fournisseurs et données d'usage sont intactes.", "ui.artificial_analysis_api_key":"Clé API Artificial Analysis", "ui.optional":"(facultatif)", "ui.save_key":"Enregistrer la clé", "ui.remove_stored_key":"Supprimer la clé enregistrée", "ui.how_quality_scoring_works":"Comment fonctionne le score de qualité", "ui.paste_it_above_and_save_it_is_encrypted_":"Collez-la ci-dessus et enregistrez. Elle est chiffrée au repos, et tout ce qui était en cache est écarté pour que le prochain rafraîchissement utilise la nouvelle clé.", "ui.quality_scores":"Scores de qualité", "ui.where_these_numbers_come_from":"D'où viennent ces chiffres", "ui.manual":"Manuel", "ui.effective":"Effectif", "ui.m_blended":"$/M combiné", "ui.help_and_docs":"Aide et docs", "ui.what_is_geekcubo":"Qu'est-ce que GeekCubo ?", "ui.60_second_quickstart":"Démarrage rapide en 60 secondes", "ui.keyboard_shortcuts":"Raccourcis clavier", "ui.switch_tabs":"Changer d'onglet", "ui.command_palette":"Palette de commandes", "ui.toggle_this_help":"Afficher/masquer cette aide", "ui.close_drawers_palette":"Fermer les panneaux / la palette", "ui.going_further":"Pour aller plus loin", "js.ov_empty_a":"Aucune requête pour l'instant.", "js.ov_empty_b":"Dès votre premier appel, il apparaîtra ici.", "js.ra_unavailable":"Analytique de routage indisponible.", "js.no_spend":"Aucune dépense enregistrée sur cette période.", "js.no_traffic":"Pas encore de trafic", "toast.copied":"Copié dans le presse-papiers", "toast.copy_blocked":"Copie impossible — le navigateur l’a bloquée", "toast.signed_in":"Connecté en tant que {name}", "toast.admin_created":"Administrateur {name} créé", "toast.signed_out":"Déconnecté", "toast.load_providers_failed":"Impossible de charger les fournisseurs : {msg}", "toast.removed_provider":"{name} supprimé", "toast.api_key_empty":"La clé API ne peut pas être vide", "toast.saved_provider":"Clé de {name} enregistrée", "toast.load_custom_failed":"Impossible de charger les fournisseurs personnalisés : {msg}", "toast.updated":"{name} mis à jour", "toast.model_id_empty":"L’identifiant du modèle ne peut pas être vide", "toast.model_id_dup":"Cet identifiant de modèle est déjà enregistré", "toast.model_saved":"Modèle enregistré", "toast.select_one_model":"Sélectionnez au moins un nouveau modèle", "toast.added_models_one":"1 modèle ajouté", "toast.added_models_many":"{count} modèles ajoutés", "toast.load_routing_failed":"Impossible de charger le routage : {msg}", "toast.routing_strategy":"Stratégie de routage : {name}", "toast.policy_saved":"Politique de routage enregistrée", "toast.load_models_failed":"Impossible de charger les modèles : {msg}", "toast.load_analytics_failed":"Impossible de charger l’analytique : {msg}", "toast.load_keys_failed":"Impossible de charger les clés : {msg}", "toast.revoked":"{name} révoquée", "toast.name_empty":"Le nom ne peut pas être vide", "toast.key_renamed":"Clé renommée", "toast.name_first":"Donnez d’abord un nom à la clé", "toast.created":"{name} créée", "toast.load_security_failed":"Impossible de charger la sécurité : {msg}", "toast.password_updated":"Mot de passe mis à jour — autres appareils déconnectés", "toast.load_quality_failed":"Impossible de charger les scores : {msg}", "toast.score_range":"Le score doit être un nombre entre 0 et 100", "toast.override_set":"Remplacement défini pour {name}", "toast.reset":"{name} réinitialisé", "toast.aa_saved":"Clé Artificial Analysis enregistrée", "toast.stored_removed":"Clé enregistrée supprimée", "toast.remove_key_failed":"Impossible de supprimer la clé : {msg}", "toast.aa_refreshed":"Scores d’Artificial Analysis actualisés", "toast.refresh_failed":"Échec de l’actualisation : {msg}", "toast.load_profiles_failed":"Impossible de charger les profils : {msg}", "toast.duplicated":"{name} dupliqué", "toast.now_default":"{name} est désormais le défaut", "toast.deleted":"{name} supprimé", "toast.default_reassigned":" — le défaut est désormais auto", "toast.saved_profile":"{name} enregistré", "toast.file_too_large":"Ce fichier est trop volumineux pour un export de profil.", "toast.load_integrations_failed":"Impossible de charger les intégrations : {msg}", "toast.load_mi_failed":"Impossible de charger les sources de données : {msg}", "toast.source_added":"Source ajoutée", "toast.legacy_removed":"Entrée héritée « __custom__ » supprimée", "toast.saved_as":"{name} enregistré comme {slug}. Récupérez ses modèles ci-dessous.", "confirm.remove_provider":"Supprimer la clé de {name} ? Les requêtes routées vers {name} échoueront.", "confirm.remove_model":"Supprimer le modèle {name} ?", "confirm.remove_custom":"Supprimer le fournisseur « {name} » et ses modèles ?", "confirm.sign_out_others":"Déconnecter tous les autres navigateurs de cet administrateur ?", "confirm.reset_score":"Réinitialiser {name} à son score AA ?", "confirm.remove_aa_key":"Supprimer la clé Artificial Analysis enregistrée ? Une clé d’environnement reprend le relais si elle existe.", "confirm.change_slug":"Changer l’identifiant API de « {old} » en « {new} » ?\n\nTout client envoyant model: « {old} » cessera de fonctionner.", "confirm.delete_source":"Supprimer cette source de métadonnées ?", "confirm.legacy_remove":"Supprimer définitivement la clé fournisseur héritée « __custom__ » ({prefix}) ?\n\nElle ne sert pas au routage. Assurez-vous d’avoir la clé sauvegardée ailleurs si besoin — elle est irrécupérable.", "confirm.revoke":"Révoquer « {name} » ?\n\nLes clients utilisant cette clé reçoivent immédiatement un 401. Irréversible — émettez une nouvelle clé si nécessaire.", "confirm.rotate":"Faire tourner « {name} » ?\n\nUne clé de remplacement avec les mêmes restrictions est créée et affichée une seule fois.\n\nOK = révoquer l’ancienne clé maintenant.\nAnnuler = garder l’ancienne clé active jusqu’à révocation manuelle.", "prompt.rename_key":"Renommer la clé « {name} » en :", "prompt.set_score":"Définir le score de qualité manuel de {name} (0-100) :", "prompt.aa_current":"Le score AA actuel est : {score}", "prompt.override_note":"Note facultative (pourquoi ce remplacement ?) :", "auth.session_expired":"Votre session a expiré. Reconnectez-vous.", "auth.enter_creds":"Saisissez votre nom d’utilisateur et votre mot de passe.", "auth.creds_required":"Le nom d’utilisateur et le mot de passe sont requis.", "auth.pw_mismatch":"Les mots de passe ne correspondent pas.", "auth.paste_token":"Collez le jeton de configuration à usage unique du journal du serveur.", "auth.signed_out":"Déconnecté.", "auth.pw_match":"Les mots de passe correspondent.", "auth.pw_mismatch_yet":"Les mots de passe ne correspondent pas encore.", "auth.new_pw_mismatch":"Les nouveaux mots de passe ne correspondent pas.", "auth.fill_three":"Remplissez les trois champs.", "qa.connection":"Connexion Artificial Analysis", "qa.test":"Tester la connexion", "qa.replace":"Remplacer la clé", "qa.add":"Ajouter une clé", "qa.remove":"Supprimer la clé", "qa.last_sync":"Dernière synchronisation réussie", "qa.last_error":"Dernière erreur", "qa.never":"jamais synchronisé", "qa.from_env":"depuis l'environnement", "qa.saving":"Enregistrement…", "qa.key_hint":"Chiffrée sur ce serveur et jamais réaffichée. La clé précédente reste active jusqu'à l'enregistrement de celle-ci.", "qa.daily_limit_label":"Limite quotidienne de votre clé", "qa.daily_limit_hint":"Requêtes par 24 h, selon votre page de compte Artificial Analysis. Laissez vide pour la limite documentée de 100/jour.", "qa.status.not_configured":"Non configurée", "qa.status.connected":"Connectée", "qa.status.invalid_key":"Clé invalide", "qa.status.rate_limited":"Limite atteinte", "qa.status.connection_failed":"Échec de connexion", "qa.status.cached":"Données en cache", "pricing.legend":"Tarification", "pricing.allow_estimates":"Autoriser les estimations de référence dans Auto, Le moins cher et les plafonds de coût", "pricing.allow_estimates_help":"Désactivé par défaut. Seuls les prix fournisseur confirmés sont comparés ; les modèles n’ayant qu’une estimation de référence restent hors d’Auto. Une fois activé, chaque décision fondée sur une estimation est signalée.", "confirm.bulk_remove_models":"Supprimer {count} modèle(s) sélectionné(s) ? Les requêtes épinglées vers eux échoueront.", "nav.chat":"Discussions", "tab.chat.title":"Discussions", "tab.chat.sub":"Discutez avec vos modèles déployés. Routage, cache et comptage comme le trafic SDK.", "ui.open_chat":"Ouvrir le chat", "ui.open_chat_hint":"Discutez avec vos modèles déployés depuis le navigateur — même routage, cache et suivi des coûts que le trafic SDK.", "chat.new":"Nouveau chat", "chat.settings_title":"Paramètres du chat", "chat.default_title":"Nouveau chat", "chat.clear_history":"Effacer l'historique…", "chat.conversations_aria":"Discussions", "chat.model_aria":"Modèle", "chat.regenerate":"Régénérer la réponse", "chat.empty_title":"Posez n'importe quelle question.", "chat.empty_sub":"Les requêtes passent par le moteur — même routage, cache et suivi des coûts que le trafic SDK.", "chat.input_placeholder":"Message à GeekCubo…", "chat.send":"Envoyer", "chat.stop":"Arrêter", "chat.system_prompt":"Prompt système…", "chat.system_prompt_set":"Prompt système ✓", "chat.system_ph":"Tu es un assistant utile…", "chat.system_help":"Vide = utiliser la valeur par défaut du chat. Enregistré par conversation.", "chat.save_prompt":"Enregistrer le prompt", "chat.default_model":"Modèle par défaut", "chat.default_model_help":"Utilisé pour les nouvelles conversations. Le sélecteur de la conversation prime.", "chat.temperature":"Température", "chat.max_tokens":"Tokens de sortie max", "chat.default_system_prompt":"Prompt système par défaut", "chat.default_system_prompt_ph":"Tu es un assistant d'ingénierie concis.", "chat.default_system_help":"S'applique aux conversations sans leur propre prompt.", "chat.save_history":"Enregistrer l'historique des discussions sur ce serveur", "chat.retention_days":"Conserver les conversations (jours)", "chat.retention_help":"Les conversations plus anciennes sont supprimées. Vide = tout conserver.", "chat.font_size":"Taille du texte des messages", "chat.fs_small":"Petit", "chat.fs_medium":"Moyen", "chat.fs_large":"Grand", "chat.enter_to_send":"Entrée envoie le message", "chat.privacy_note":"Les conversations restent dans la base de données de ce serveur. Les requêtes sont envoyées aux fournisseurs configurés, exactement comme le trafic SDK.", "chat.privacy_ack":"Je comprends que le trafic de chat est envoyé aux fournisseurs configurés", "chat.save_settings":"Enregistrer les paramètres", "chat.model_auto":"Auto (le routeur choisit)", "chat.no_conversations":"Aucune conversation pour l'instant.", "chat.delete_convo_title":"Supprimer cette conversation", "chat.kbd_enter_send":"Entrée pour envoyer · Maj+Entrée pour un saut de ligne", "chat.kbd_ctrl_enter_send":"Ctrl+Entrée pour envoyer · Entrée pour un saut de ligne", "chat.tokens_meta":"{in} entrée · {out} sortie", "chat.error_note":"La génération s'est arrêtée avant la fin.", "chat.upstream_error":"Le modèle amont a renvoyé une erreur.", "toast.chat_load_failed":"Impossible de charger les données de chat : {msg}", "toast.chat_failed":"Échec de la requête de chat : {msg}", "toast.chat_convo_deleted":"Conversation supprimée", "toast.chat_cleared":"{count} conversations effacées", "toast.chat_temp_range":"La température doit être comprise entre 0 et 2", "toast.chat_settings_saved":"Paramètres du chat enregistrés", "toast.chat_open_convo":"Ouvrez d'abord une conversation", "toast.chat_saved_prompt":"Prompt système enregistré pour cette conversation", "confirm.delete_conversation":"Supprimer cette conversation ?\n\nLes messages sont retirés de la base de données du serveur. Les enregistrements d'usage et de coûts restent dans les analyses.", "confirm.clear_chat_history":"Supprimer TOUTES les conversations enregistrées ?\n\nTous les messages de chat stockés sur ce serveur sont supprimés. Les enregistrements d'usage et de coûts restent dans les analyses.", "q.ov_score":"Score manuel (0–100)", "q.ov_note":"Remarque", "q.ov_model_ph":"ex. openai/gpt-4o, anthropic/claude-…", "q.ov_note_ph":"Pourquoi cette valeur remplace le score AA", "q.ov_apply":"Appliquer la substitution", "q.ov_clear":"Supprimer la substitution", "q.ov_help":"Un ou plusieurs ids de modèle, séparés par des virgules — la substitution s'applique à chaque modèle listé. Les scores manuels l'emportent toujours sur les scores AA.", "toast.q_ids_required":"Saisissez au moins un id de modèle", "toast.q_too_many":"L'opération groupée est limitée à 500 ids de modèle", "toast.q_bulk_set":"Substitution appliquée à {count} modèle(s)", "toast.q_bulk_clear":"Substitutions supprimées pour {count} modèle(s)", "providers.bulk_actions":"Actions groupées sur les modèles", "providers.select_all":"Tout sélectionner", "providers.selected_count":"{count} sélectionné(s)", "providers.bulk_capability":"Capacité", "providers.bulk_capability_state":"État de la capacité", "providers.cap_tools":"Outils", "providers.cap_vision":"Analyse d’images", "providers.cap_supported":"Pris en charge", "providers.cap_unsupported":"Non pris en charge", "providers.cap_unknown":"Inconnu", "providers.cap_catalog":"Utiliser le catalogue", "providers.cap_json_mode":"Mode JSON", "providers.cap_json_schema":"Schéma JSON", "providers.apply":"Appliquer", "providers.enable":"Activer", "providers.disable":"Désactiver", "providers.remove_selected":"Retirer la sélection", "providers.resolve_metadata":"Résoudre", "toast.metadata_resolved":"Métadonnées : {resolved} résolues, {ambiguous} ambiguës, {unmatched} sans correspondance, {failed} échecs.", "select.search_ph":"Rechercher des clés de catalogue…", "providers.catalog_key_ph":"Rechercher des clés de catalogue…", "select.remove_item":"Retirer {name}", "select.use_custom":"Utiliser « {name} »", "select.no_matches":"Aucun modèle correspondant", "select.more_results":"{count} de plus — continuez à taper pour affiner", "q.ov_model_search_ph":"Rechercher et choisir des modèles…", "q.ov_help_picker":"Recherchez et choisissez un ou plusieurs modèles, ou cochez des lignes dans le tableau ci-dessous. Les scores manuels l’emportent toujours sur ceux d’AA.", "q.filter_ph":"Filtrer les modèles…", "q.select_filtered":"Sélectionner les filtrés", "q.select_all_filtered":"Sélectionner tous les modèles filtrés", "q.deselect_all":"Tout désélectionner", "q.bulk_set":"Noter la sélection", "q.bulk_clear":"Effacer les remplacements sélectionnés", "q.select_model":"Sélectionner {name}", "confirm.q_bulk_clear":"Effacer les remplacements manuels de {count} modèles sélectionnés ?", "qa.daily_limit_short":"Limite quotidienne", "chat.attach":"Joindre des fichiers", "chat.attach_drop":"Déposez des fichiers pour les joindre", "chat.attach_remove":"Retirer la pièce jointe", "chat.attach_unreadable":"Ce fichier n'a pas pu être lu ; seul son nom est envoyé.", "chat.attach_uploading":"Envoi…", "chat.attach_too_large":"Trop volumineux (max. {max} Mo)", "toast.chat_attach_failed":"Impossible de joindre {name} : {msg}", "toast.chat_attach_disabled":"Les pièces jointes sont désactivées sur ce serveur.", "toast.chat_attach_too_many":"Au plus {max} pièces jointes par message.", "toast.chat_attach_extract_failed":"{name} : lecture impossible ({msg})", "toast.chat_attach_wait":"Attendez la fin des envois.", "chat.search_toggle":"Recherche web", "chat.search_settings":"Recherche web", "chat.search_help":"Une fois activée, GeekCubo cherche sur le web avant de répondre et cite les pages utilisées. Les résultats sont injectés comme message système, donc tout modèle peut les exploiter.", "chat.search_mode":"Mode de recherche", "chat.search_mode_off":"Désactivée", "chat.search_mode_manual":"Manuel (par message)", "chat.search_mode_auto":"Automatique (réservé)", "chat.search_mode_help":"Le mode manuel affiche un bouton dans la zone de saisie. L'automatique est réservé et pas encore implémenté.", "chat.search_backend":"Moteur de recherche", "chat.search_backend_none":"Choisir un moteur…", "chat.search_backend_searxng":"SearXNG (auto-hébergé)", "chat.search_backend_brave":"API Brave Search", "chat.search_backend_tavily":"Tavily", "chat.search_url":"URL SearXNG", "chat.search_url_ph":"http://searxng:8080/", "chat.search_url_help":"URL de base de votre instance SearXNG. Le profil search de l'installateur la sert sur le réseau interne.", "chat.search_api_key":"Clé d'API", "chat.search_api_key_ph":"Collez une nouvelle clé pour remplacer celle enregistrée", "chat.search_key_clear":"Supprimer la clé enregistrée", "chat.search_key_help":"Stockée chiffrée sur ce serveur et plus jamais affichée. Brave et Tavily exigent une clé ; SearXNG non.", "chat.search_max_searches":"Recherches max par conversation", "chat.search_max_results":"Résultats par recherche", "chat.search_max_fetches":"Pages récupérées par recherche", "chat.search_timeout":"Délai de recherche (secondes)", "chat.search_test":"Tester la connexion", "chat.search_testing":"Test en cours…", "chat.search_test_ok":"{count} résultats en {ms} ms", "chat.search_test_failed":"Échec du test de recherche : {msg}", "chat.search_key_state_unset":"Aucune clé enregistrée", "chat.search_key_state_set":"Clé enregistrée", "chat.search_key_state_undecryptable":"La clé enregistrée ne peut pas être déchiffrée", "chat.context_budget":"Contexte : {tokens} / {budget} tokens", "chat.context_omitted":"{count} messages précédents omis", "chat.sources":"Références", "chat.search_used":"recherche web : {backend}", "toast.search_saved":"Paramètres de recherche web enregistrés", "toast.search_save_failed":"Impossible d'enregistrer les paramètres de recherche : {msg}", "toast.search_test_failed":"Le test de recherche web a échoué", "nav.local":"IA locale", "tab.local.title":"IA locale", "tab.local.sub":"Servez des modèles depuis vos propres machines via ce routeur.", "local.title":"Connexion IA locale", "local.sub":"Acheminez vers des modèles exécutés sur vos propres machines. Un petit connecteur se connecte à ce serveur, donc aucun port n'est ouvert et aucun tunnel entrant n'est nécessaire.", "local.refresh":"Actualiser", "local.setup_button":"Configurer une machine", "local.feature_off_title":"La connexion IA locale est désactivée sur le serveur", "local.feature_off_body":"Définissez LOCAL_CONNECT_ENABLED=true dans l'environnement du serveur et redémarrez, puis rechargez cette page.", "local.url_missing_title":"Aucune URL publique configurée", "local.url_missing_body":"Définissez LOCAL_CONNECT_PUBLIC_URL avec l'adresse que les connecteurs doivent joindre (par exemple https://example.com) pour que la commande d'installation et les fichiers de service soient remplis.", "local.settings_title":"Comportement du routage", "local.settings_sub":"Détermine si les modèles locaux participent à Auto et si une requête peut basculer vers le cloud.", "local.set_enabled":"Autoriser les machines locales pour le routage", "local.set_auto":"Inclure les modèles locaux dans la sélection automatique", "local.set_no_fallback":"Ne jamais basculer vers le cloud en cas d'échec d'un modèle local", "local.settings_help":"Les modèles locaux ne sont pris en compte pour Auto que si leur prix est confirmé à zéro et que la machine est approuvée et en ligne. Avec « ne jamais basculer » activé, une requête purement locale échoue au lieu d'être servie par un fournisseur cloud.", "local.save_settings":"Enregistrer", "local.settings_saved":"Paramètres de routage local enregistrés.", "local.machines_title":"Postes", "local.machines_sub":"Chaque machine correspond à un connecteur. Les machines en attente sont visibles mais ne reçoivent aucun trafic avant approbation.", "local.machines_empty":"Aucune machine pour l'instant. Utilisez « Configurer une machine » pour générer un code d'inscription.", "local.enrollments_title":"Codes d'inscription", "local.enrollments_sub":"Des codes à usage unique permettant à un connecteur de s'enregistrer. Chaque code est consommé à la première connexion d'une machine.", "local.new_code":"Nouveau code", "local.install_title":"Installer le connecteur", "local.install_sub":"Exécutez ceci sur la machine qui héberge vos modèles (Ollama, LM Studio, vLLM, llama.cpp ou tout serveur compatible [OI]).", "local.service_files":"L'exécuter comme service", "local.delete":"Supprimer", "local.never":"jamais", "local.ctx_suffix":"contexte", "local.ctx_unknown":"contexte inconnu", "local.no_models":"Cette machine n'a encore signalé aucun modèle.", "local.no_enrollments":"Aucun code d'inscription.", "local.enroll_active":"Actif", "local.enroll_used":"Utilisé", "local.status_online":"En ligne", "local.status_offline":"Hors ligne", "local.status_pending":"En attente d'approbation", "local.status_approved":"Approuvée", "local.status_revoked":"Révoquée", "local.pending_note":"Cette machine attend une approbation. Les modèles sont listés mais aucun trafic ne leur sera envoyé.", "local.action_approve":"Approuver", "local.action_discover":"Découvrir les modèles", "local.action_revoke":"Révoquer", "local.action_rotate":"Renouveler l'identifiant", "local.action_delete":"Supprimer", "local.meta_host":"Nom d'hôte", "local.meta_platform":"Plateforme", "local.meta_agent":"Version du connecteur", "local.meta_adapters":"Adaptateurs", "local.meta_seen":"Vu pour la dernière fois", "local.col_model":"Modèle", "local.col_adapter":"Type d'adaptateur", "local.col_context":"Contexte", "local.col_caps":"Capacités", "local.col_enabled":"Activé", "local.kpi_machines":"Postes", "local.kpi_online":"En ligne maintenant", "local.kpi_pending":"En attente d'approbation", "local.kpi_models":"Modèles", "local.toast_approved":"Machine approuvée.", "local.toast_revoked":"Machine révoquée.", "local.toast_deleted":"Machine supprimée.", "local.toast_discovered":"Liste des modèles actualisée.", "local.confirm_revoke":"Révoquer cette machine ? Son connecteur est déconnecté immédiatement et ne pourra se reconnecter qu'après renouvellement de son identifiant.", "local.confirm_delete_machine":"Supprimer cette machine et sa liste de modèles ? Cette action est irréversible.", "local.confirm_rotate":"Renouveler l'identifiant de cette machine ? Le connecteur en cours continue jusqu'à la reconnexion, puis l'ancien identifiant est rejeté.", "local.confirm_delete_enrollment":"Supprimer ce code d'inscription ?", "local.credential_once_title":"Copiez le nouvel identifiant maintenant", "local.credential_once_body":"Il n'est affiché qu'une seule fois. Enregistrez-le dans la configuration du connecteur sur la machine.", "local.wizard_title":"Connecter une machine locale", "local.wizard_close":"Fermer", "local.wizard_back":"Retour", "local.wizard_next":"Suivant", "local.wizard_done":"Terminé", "local.step1":"Activer", "local.step2":"Code d'inscription", "local.step3":"Installer", "local.step4":"Inscrire", "local.step5":"Démarrer", "local.step6":"Approuver", "local.step7":"Modèles", "local.step8":"Routage automatique", "local.w0_title":"Activez la fonction", "local.w0_body":"La connexion IA locale est une fonction côté serveur. Elle doit être activée avant que les connecteurs puissent s'enregistrer.", "local.w0_ready":"La fonction est activée. Continuez pour créer un code d'inscription.", "local.w0_blocked":"La fonction est désactivée sur ce serveur. Définissez LOCAL_CONNECT_ENABLED=true et redémarrez, puis rechargez cette page.", "local.w1_title":"Créez un code d'inscription", "local.w1_body":"Un code à usage unique autorise un seul connecteur à s'enregistrer. Il expire après un court délai.", "local.w1_name":"Nom de la machine (facultatif)", "local.w1_name_ph":"ex. bureau-gpu", "local.w1_name_help":"Un libellé pour reconnaître cette machine dans la liste. Vous pourrez la renommer plus tard.", "local.w1_created":"Code d'inscription créé", "local.w2_title":"Installez le paquet du connecteur", "local.w2_body":"Sur la machine qui héberge vos modèles, installez le connecteur. Python 3.11 ou plus récent est requis.", "local.w2_note":"Installez-le dans un environnement virtuel pour l'isoler des paquets système.", "local.w3_title":"Inscrivez la machine", "local.w3_body":"Exécutez la commande d'inscription avec le code de l'étape 2. L'identifiant est écrit dans le fichier de configuration du connecteur.", "local.w3_note":"Le code est à usage unique. S'il a expiré, créez-en un nouveau.", "local.w4_title":"Démarrez le connecteur", "local.w4_body":"Exécutez le connecteur au premier plan pour voir la connexion, puis transformez-le en service.", "local.w4_note":"Le connecteur maintient une seule WebSocket sortante ouverte et se reconnecte automatiquement.", "local.w5_title":"Attendez que la machine apparaisse", "local.w5_body":"Dès que le connecteur se connecte, la machine apparaît ici. Actualisez si cela prend un moment.", "local.w5_seen":"{name} s'est connectée.", "local.w5_waiting":"Aucune machine ne s'est encore connectée.", "local.w5_recheck":"Vérifier à nouveau", "local.w6_title":"Approuvez la machine", "local.w6_body":"Une nouvelle machine reste en attente jusqu'à ce qu'un administrateur l'approuve. Rien ne lui est acheminé avant.", "local.w6_none":"Aucune machine à approuver pour l'instant.", "local.w6_must_approve":"Approuvez la machine en attente avant de continuer.", "local.w7_title":"Activez les modèles locaux dans Auto", "local.w7_body":"Activez « Inclure les modèles locaux dans la sélection automatique » et activez les modèles souhaités. Les modèles locaux ne sont choisis pour Auto que si leur prix est confirmé à zéro.", "local.w7_done":"La configuration est terminée. Les modèles locaux apparaissent désormais dans les pages Fournisseurs et Routage." },
  it: { "q.tabs_label":"Sezioni qualità", "q.tab_models":"Modelli", "q.tab_scores":"Punteggi di qualità", "q.tab_aa":"Connessione Artificial Analysis", "q.col_availability":"Disponibilità", "q.avail_yes":"disponibile", "q.avail_no":"nessuna chiave provider", "q.avail_no_title":"Nessuna chiave provider configurata serve questo modello. I soli dati di benchmark non rendono un modello distribuibile.", "q.sync_title":"Sincronizzazione dei benchmark", "q.sync_last_ok":"Ultima sincronizzazione riuscita", "q.sync_last_attempt":"Ultimo tentativo", "q.sync_returned":"Modelli restituiti da AA", "q.sync_matched":"Abbinati al catalogo", "q.sync_unmatched":"Non abbinati", "q.sync_overrides":"Punteggi manuali", "q.sync_outcome_ok":"riuscita", "q.sync_outcome_failed":"non riuscita", "q.sync_need_key":"Aggiungi una chiave nella scheda Artificial Analysis per sincronizzare i punteggi. I punteggi manuali funzionano senza chiave.", "q.sync_never":"Con questa chiave non è ancora stata eseguita alcuna sincronizzazione. Usa Aggiorna da AA.", "q.sync_no_models":"L'ultima sincronizzazione non ha restituito modelli.", "q.status_line":"{matched} modelli con dati di benchmark · {overrides} punteggi manuali", "q.src.live":"aggiornato", "q.src.stale_cache":"in cache (AA non raggiungibile)", "q.src.stale_db":"in cache (istantanea salvata)", "q.src.error":"sincronizzazione non riuscita", "q.src.missing_key":"nessuna chiave API", "q.auto_status":"Stato del routing automatico", "q.auto_status_hint":"Cosa sceglierebbe ora model=\"auto\". Dipende dai provider configurati, non dalla sincronizzazione dei benchmark.", "q.auto_no_provider":"Nessun modello distribuibile soddisfa i requisiti attuali. Aggiungi una chiave nella pagina Provider. Non dipende dalla sincronizzazione con Artificial Analysis.", "qa.credential":"Chiave API", "qa.cred_stored":"Salvata su questo server (cifrata)", "qa.cred_env":"Dall'ambiente del server", "qa.last_test":"Ultimo test di connessione", "qa.last_test_ok":"Ultimo test riuscito", "qa.not_tested":"Non ancora testata", "qa.sync_status":"Sincronizzazione", "qa.tier":"piano {tier}", "qa.troubleshooting":"Risoluzione dei problemi di connessione", "qa.status.key_configured":"Chiave configurata", "qa.sync.not_configured":"Non configurato", "qa.sync.never_synced":"Mai sincronizzato", "qa.sync.synced":"Sincronizzato", "qa.sync.sync_failed":"Sincronizzazione non riuscita", "qa.err.invalid_key":"Chiave non valida", "qa.err.insufficient_tier":"Il piano non include l'endpoint", "qa.err.endpoint_retired":"Endpoint dismesso", "qa.err.rate_limited":"Limite di richieste raggiunto", "qa.err.timeout":"Tempo scaduto", "qa.err.malformed_response":"Risposta inattesa", "qa.err.no_data":"Nessun modello restituito", "qa.err.no_catalog_match":"Nessuna corrispondenza nel catalogo", "qa.err.server_error":"Errore del server AA", "qa.err.connection_failed":"Connessione non riuscita", "auth.tagline":"Un gateway. Tutti i modelli di IA.", "auth.welcome":"Bentornato", "auth.subtitle":"Accedi alla console di amministrazione di questa installazione di GeekCubo.", "auth.api_key":"Chiave API", "auth.continue":"Continua", "nav.search":"Cerca", "nav.overview":"Panoramica", "nav.providers":"Provider", "nav.routing":"Smistamento", "nav.analytics":"Analitica", "nav.api_keys":"Chiavi API", "nav.help_docs":"Aiuto e documentazione", "nav.sign_out":"Disconnetti", "status.connected":"Connesso", "status.disconnected":"Disconnesso", "auth.checking":"Verifica…", "auth.welcome_aboard":"Benvenuto.", "auth.key_invalid":"La chiave non ha funzionato. Controlla il prefisso sk-geek-…", "tab.overview.title":"Panoramica", "tab.overview.sub":"Il tuo router LLM single-tenant a colpo d'occhio.", "tab.providers.title":"Chiavi provider", "tab.providers.sub":"BYOK — crittografate a riposo, usate per chiamare LLM upstream.", "tab.routing.title":"Instradamento", "tab.routing.sub":"Come model='auto' sceglie il modello giusto per ogni richiesta.", "tab.analytics.title":"Analitica", "tab.analytics.sub":"Spesa locale, latenza e cronologia richieste.", "tab.keys.title":"Chiavi API", "tab.keys.sub":"Chiavi sk-geek-* che autenticano il traffico di inferenza SDK e CLI.", "nav.quality":"Qualità", "tab.quality.title":"Punteggi di qualità", "tab.quality.sub":"Punteggi benchmark reali per la strategia di instradamento per qualità. Da Artificial Analysis.", "auth.username":"Nome utente", "auth.password":"Password", "auth.sign_in":"Accedi", "nav.security":"Sicurezza", "tab.security.title":"Sicurezza", "tab.security.sub":"Account amministratore, password e sessioni.", "tab.profiles.title":"Profili di instradamento", "tab.profiles.sub":"Configurazioni Auto con nome che i client scelgono per id del modello.", "tab.integrations.title":"Connetti uno strumento", "tab.integrations.sub":"Configurazione pronta per OpenCode, Claude Code, Cursor e altri.", "tab.intelligence.title":"Dati dei modelli", "tab.intelligence.sub":"Da dove provengono prezzi e limiti dei modelli.", "auth.loading":"Caricamento…", "auth.checking_status":"Verifica dello stato dell'amministratore.", "auth.signin_title":"Accedi", "auth.signin_sub":"Accesso amministratore a questa installazione di GeekCubo.", "auth.forgot":"Password dimenticata?", "auth.reset_hint":"Reimpostala sull'host o nel contenitore:", "auth.reset_note":"Chiavi, provider e utilizzo non sono interessati.", "auth.setup_title":"Crea account amministratore", "auth.setup_sub":"Controlla questa installazione di GeekCubo: credenziali dei provider, chiavi API e instradamento.", "auth.min_password":"Minimo 8 caratteri", "auth.confirm_password":"Conferma password", "auth.setup_token":"Token di configurazione", "auth.from_log":"Dal log del server", "auth.create_admin":"Crea amministratore", "auth.where_token":"Dove si trova il token di configurazione?", "auth.token_hint":"Stampato nel log del server al primo avvio. Per emetterne uno nuovo:", "auth.toggle_password":"Mostra o nascondi la password", "ov.spend":"Spesa (7 g)", "ov.savings":"Risparmio da instradamento", "ov.p50":"latenza p50", "ov.models":"Modelli distribuibili", "ov.quickstart":"Avvio rapido", "ov.recent":"Attività recente", "prov.title":"Chiavi provider", "prov.tab_std":"Provider standard", "prov.tab_custom":"Provider personalizzati", "routing.strategy":"Strategia di instradamento", "routing.pools":"Pool di modelli", "routing.advanced":"Fallback, escalation e continuità", "routing.explain":"Prova una decisione di instradamento", "profiles.title":"Profili di instradamento", "int.title":"Connetti il tuo strumento IA", "md.title":"Sorgenti dati dei modelli", "md.lookup":"Ricerca prezzi", "an.spend":"Spesa per modello", "an.latency":"Latenza per provider", "an.recent":"Richieste recenti", "keys.title":"Chiavi API del router", "sec.sessions":"Sessioni", "q.setup":"Configura il punteggio di qualità", "q.models":"Modelli", "preset.heading":"Inizia da un modello", "preset.sub":"I modelli aprono l’editor già compilato: modifica tutto prima di salvare.", "preset.economy":"Il modello capace più economico per ogni richiesta. Spesa minima, nessun limite di qualità.", "preset.premium":"Prima i modelli più forti, prezzo ignorato. Per lavori in cui la qualità conta.", "preset.coding":"Chiamate agli strumenti e prompt lunghi vanno al pool Hard. Per agenti ed editor.", "preset.fast":"Instradamento bilanciato che preferisce latenza più bassa nel pool.", "ui.profiles":"Profili", "ui.security":"Sicurezza", "ui.api_keys":"Chiavi API", "ui.connect_a_tool":"Connetti uno strumento", "ui.model_data":"Dati dei modelli", "ui.connecting":"Connessione…", "ui.language":"Lingua", "ui.light":"Chiaro", "ui.system":"Sistema", "ui.dark":"Scuro", "ui.openai_compatible_base_url":"URL di base compatibile OpenAI", "ui.copy":"Copia", "ui.use_this_in_any_openai_compatible_client":"Usala in qualsiasi client compatibile OpenAI.", "ui.signed_in":"Accesso effettuato", "ui.security_and_sessions":"Sicurezza e sessioni", "ui.api_keys_2":"Chiavi API", "ui.sign_out":"Disconnetti", "ui.you_re_up_point_any_openai_sdk_at_your_b":"Tutto pronto: punta qualsiasi SDK OpenAI al tuo URL di base.", "ui.last_5_requests_routed_through_this_serv":"Ultime 5 richieste instradate da questo server.", "ui.view_all":"Vedi tutte", "ui.no_requests_yet":"Nessuna richiesta per ora.", "ui.new_here_get_fully_set_up_in_2_minutes":"Prima volta? Configura tutto in 2 minuti", "ui.re_enter_as_a_named_provider":"Reinserisci come provider denominato", "ui.remove_legacy_entry":"Rimuovi voce legacy", "ui.provider":"Provider", "ui.others_openai_format":"Altri (formato OpenAI)", "ui.api_key":"Chiave API", "ui.provider_name":"Nome provider", "ui.display_name_a_unique_internal_slug_is_d":"Nome visualizzato. Uno slug interno univoco viene derivato automaticamente.", "ui.api_base_url":"URL di base API", "ui.usually_ends_in_v1_must_be_https_unless_":"Di solito termina con /v1. Deve essere https salvo che l'host sia in CUSTOM_PROVIDER_ALLOWED_LOCAL_HOSTS.", "ui.api_key_2":"Chiave API", "ui.encrypted_at_rest_never_displayed_again_":"Crittografata a riposo. Non viene mai più mostrata dopo il salvataggio.", "ui.prefix":"Prefisso", "ui.status":"Stato", "ui.no_provider_keys_yet":"Nessuna chiave provider", "ui.add_at_least_one_to_start_routing_real_t":"Aggiungine almeno una per iniziare a instradare traffico reale. Scegli un provider sopra o clicca un suggerimento rapido.", "ui.lowest_cost_that_clears_your_quality_flo":"Il costo più basso che supera la tua soglia di qualità. Scelta sicura con qualsiasi numero di provider.", "ui.recommended":"Consigliato", "ui.lowest_per_token_cost_meeting_the_reques":"Il costo per token più basso che soddisfa le capacità della richiesta. La qualità dell'output può variare.", "ui.highest_score_from_artificial_analysis_o":"Il punteggio più alto da Artificial Analysis o dalle tue sostituzioni manuali. Senza punteggi usa il prezzo come approssimazione.", "ui.re_ranks_by_observed_success_rate_and_la":"Riordina per tasso di successo e latenza osservati quando un modello raggiunge 20+ richieste qui. Fino ad allora: Bilanciato.", "ui.sends_each_request_to_your_mundane_or_ha":"Invia ogni richiesta al pool Mundane o Hard in base a segnali osservabili (strumenti, dimensione, lunghezza).", "ui.highest_throughput_and_lowest_first_toke":"Massima velocità e minima latenza del primo token dai dati di benchmark. Mantenuto per compatibilità.", "ui.legacy":"Legacy", "ui.registered_models":"Modelli registrati", "ui.show":"Mostra", "ui.deployable":"Distribuibili", "ui.custom_providers":"Provider personalizzati", "ui.model":"Modello", "ui.capabilities":"Capacità", "ui.context":"Contesto", "ui.price_1m_in_out":"Prezzo /1M (in · out)", "ui.availability":"Disponibilità", "ui.pools":"Pool", "ui.previous":"Precedente", "ui.next":"Successivo", "ui.fallback_and_escalation_always_keep_the_":"Fallback ed escalation preservano sempre le capacità richieste. Le decisioni avvengono prima dell'avvio; i modelli non cambiano mai a metà stream.", "ui.maximum_attempts_primary_fallbacks":"Tentativi massimi (primario + fallback)", "ui.what_counts_as_retryable":"Cosa conta come ritentabile", "ui.quality_floor_percentile_0_off":"Soglia di qualità (percentile, 0 = disattivata)", "ui.needs_quality_scores_ignored_and_reporte":"Richiede punteggi di qualità; viene ignorata (e segnalata) se non ce ne sono.", "ui.what_the_quality_floor_does":"Cosa fa la soglia di qualità", "ui.balanced_weighs_price_against_quality_th":"Bilanciato pesa prezzo e qualità. La soglia esclude i modelli sotto quel percentile, così un modello molto economico ma debole non può vincere. Imposta 0 per disattivarla del tutto.", "ui.messages":"Messaggi ≥", "ui.prompt_characters":"Caratteri del prompt ≥", "ui.how_request_signals_are_measured":"Come vengono misurati i segnali della richiesta", "ui.mode":"Modalità", "ui.off":"Disattivato", "ui.manual_client_sends_x_geek_escalate":"Manuale (il client invia x-geek-escalate)", "ui.auto_after_repeated_upstream_failures":"Automatico (dopo ripetuti errori del provider)", "ui.failures_before_escalating":"Errori prima dell'escalation", "ui.max_escalations_per_conversation":"Escalation massime per conversazione", "ui.destination_pool":"Pool di destinazione", "ui.when_escalation_triggers":"Quando scatta l'escalation", "ui.remember_for_minutes":"Ricorda per (minuti)", "ui.what_continuity_does":"Cosa fa la continuità", "ui.save_routing_policy":"Salva politica di instradamento", "ui.dry_run_shows_which_model_auto_would_cho":"Simulazione: mostra quale modello sceglierebbe Auto e perché. Nulla viene inviato al provider.", "ui.messages_2":"Messaggi", "ui.prompt_chars":"Caratteri del prompt", "ui.explain":"Spiega", "ui.three_filters_applied_in_order":"Tre filtri, applicati in ordine.", "ui.how_each_strategy_maps_to_litellm_router":"Come ogni strategia si mappa su LiteLLM Router", "ui.strategy":"Strategia", "ui.import_json":"Importa JSON", "ui.new_profile":"Nuovo profilo", "ui.generates_configuration_that_points_a_cl":"Genera una configurazione che punta un client a questo GeekCubo. Le chiavi sono referenziate tramite variabile d'ambiente, mai incorporate.", "ui.search_tools":"Cerca strumenti", "ui.routing_profile_or_model":"Profilo di instradamento o modello", "ui.endpoint":"Endpoint", "ui.format":"Formato", "ui.download":"Scarica", "ui.add_source":"Aggiungi sorgente", "ui.name":"Nome", "ui.https_url_models_dev_compatible_json":"URL HTTPS (JSON compatibile con models.dev)", "ui.save_source":"Salva sorgente", "ui.cancel":"Annulla", "ui.shows_what_each_enabled_source_reports_f":"Mostra cosa riporta ogni sorgente attiva per un modello e quale valore userebbe GeekCubo. I tuoi prezzi configurati vincono sempre.", "ui.look_up":"Cerca", "ui.routing":"Instradamento", "ui.volume":"Volume", "ui.routing_decisions":"Decisioni di instradamento", "ui.how_auto_requests_were_classified_and_wh":"Come sono state classificate le richieste Auto e dove sono andate.", "ui.by_tier":"Per livello", "ui.by_strategy":"Per strategia", "ui.by_routing_id":"Per id di instradamento", "ui.top_models_served":"Modelli più serviti", "ui.reliability":"Affidabilità", "ui.errors_by_cause":"Errori per causa", "ui.compare_against_a_baseline_model":"Confronta con un modello di riferimento", "ui.none":"Nessuno", "ui.compare":"Confronta", "ui.how_the_comparison_is_calculated":"Come viene calcolato il confronto", "ui.p50_and_p99_sourced_from_local_request_l":"p50 e p99 — dai log locali delle richieste.", "ui.requests":"Richieste", "ui.newest_first_click_a_row_to_copy_its_tra":"Più recenti prima. Clicca una riga per copiarne il trace ID.", "ui.when":"Quando", "ui.tokens_in_out":"Token (in / out)", "ui.latency":"Latenza", "ui.no_traffic_yet":"Ancora nessun traffico", "ui.once_you_start_sending_requests_they_ll_":"Appena inizierai a inviare richieste, appariranno qui in tempo reale.", "ui.expires":"Scade", "ui.never":"Mai", "ui.7_days":"7 giorni", "ui.30_days":"30 giorni", "ui.90_days":"90 giorni", "ui.1_year":"1 anno", "ui.use_it_with_opencode":"Usala con OpenCode:", "ui.created":"Creata", "ui.last_used":"Ultimo uso", "ui.actions":"Azioni", "ui.no_api_keys":"Nessuna chiave API", "ui.generate_one_above_to_start_sending_requ":"Generane una sopra per iniziare a inviare richieste da un SDK o dalla CLI.", "ui.administrator":"Amministratore", "ui.the_single_local_account_that_controls_t":"L'unico account locale che controlla questa installazione.", "ui.password_was_reset_from_the_command_line":"La password è stata reimpostata da riga di comando", "ui.change_password":"Cambia password", "ui.current_password":"Password attuale", "ui.new_password":"Nuova password", "ui.confirm_new_password":"Conferma nuova password", "ui.update_password":"Aggiorna password", "ui.signed_in_browsers_for_this_administrato":"Browser con accesso per questo amministratore. Le sessioni scadono dopo 12 ore, o 60 minuti di inattività.", "ui.log_out_all_other_sessions":"Disconnetti tutte le altre sessioni", "ui.device":"Dispositivo", "ui.last_active":"Ultima attività", "ui.local_recovery":"Recupero locale", "ui.password_recovery_is_local_only_by_desig":"Il recupero della password è solo locale per scelta — nessun reset via email e nessun endpoint pubblico può cambiarla.", "ui.open_a_shell_where_geekcubo_runs_host_or":"Apri una shell dove gira GeekCubo (host o container).", "ui.choose_a_new_password_at_the_prompt_all_":"Scegli una nuova password al prompt. Tutte le sessioni della dashboard vengono disconnesse; chiavi API, provider e dati di utilizzo restano intatti.", "ui.artificial_analysis_api_key":"Chiave API Artificial Analysis", "ui.optional":"(facoltativa)", "ui.save_key":"Salva chiave", "ui.remove_stored_key":"Rimuovi chiave salvata", "ui.how_quality_scoring_works":"Come funziona il punteggio di qualità", "ui.paste_it_above_and_save_it_is_encrypted_":"Incollala sopra e salva. È crittografata a riposo e quanto già in cache viene scartato così il prossimo aggiornamento usa la nuova chiave.", "ui.quality_scores":"Punteggi di qualità", "ui.where_these_numbers_come_from":"Da dove vengono questi numeri", "ui.manual":"Manuale", "ui.effective":"Effettivo", "ui.m_blended":"$/M combinato", "ui.help_and_docs":"Aiuto e documentazione", "ui.what_is_geekcubo":"Cos'è GeekCubo?", "ui.60_second_quickstart":"Avvio rapido in 60 secondi", "ui.keyboard_shortcuts":"Scorciatoie da tastiera", "ui.switch_tabs":"Cambia scheda", "ui.command_palette":"Palette dei comandi", "ui.toggle_this_help":"Mostra o nascondi questa guida", "ui.close_drawers_palette":"Chiudi pannelli / palette", "ui.going_further":"Andando oltre", "js.ov_empty_a":"Nessuna richiesta per ora.", "js.ov_empty_b":"Appena invii la prima chiamata, apparirà qui.", "js.ra_unavailable":"Analitica di instradamento non disponibile.", "js.no_spend":"Nessuna spesa registrata in questo periodo.", "js.no_traffic":"Ancora nessun traffico", "toast.copied":"Copiato negli appunti", "toast.copy_blocked":"Copia non riuscita — il browser l’ha bloccata", "toast.signed_in":"Accesso effettuato come {name}", "toast.admin_created":"Amministratore {name} creato", "toast.signed_out":"Disconnesso", "toast.load_providers_failed":"Impossibile caricare i provider: {msg}", "toast.removed_provider":"{name} rimosso", "toast.api_key_empty":"La chiave API non può essere vuota", "toast.saved_provider":"Chiave di {name} salvata", "toast.load_custom_failed":"Impossibile caricare i provider personalizzati: {msg}", "toast.updated":"{name} aggiornato", "toast.model_id_empty":"L’ID del modello non può essere vuoto", "toast.model_id_dup":"Quell’ID di modello è già registrato", "toast.model_saved":"Modello salvato", "toast.select_one_model":"Seleziona almeno un nuovo modello", "toast.added_models_one":"1 modello aggiunto", "toast.added_models_many":"{count} modelli aggiunti", "toast.load_routing_failed":"Impossibile caricare l’instradamento: {msg}", "toast.routing_strategy":"Strategia di instradamento: {name}", "toast.policy_saved":"Politica di instradamento salvata", "toast.load_models_failed":"Impossibile caricare i modelli: {msg}", "toast.load_analytics_failed":"Impossibile caricare l’analitica: {msg}", "toast.load_keys_failed":"Impossibile caricare le chiavi: {msg}", "toast.revoked":"{name} revocata", "toast.name_empty":"Il nome non può essere vuoto", "toast.key_renamed":"Chiave rinominata", "toast.name_first":"Dai prima un nome alla chiave", "toast.created":"{name} creata", "toast.load_security_failed":"Impossibile caricare la sicurezza: {msg}", "toast.password_updated":"Password aggiornata — altri dispositivi disconnessi", "toast.load_quality_failed":"Impossibile caricare i punteggi: {msg}", "toast.score_range":"Il punteggio deve essere un numero tra 0 e 100", "toast.override_set":"Sostituzione impostata per {name}", "toast.reset":"{name} reimpostato", "toast.aa_saved":"Chiave Artificial Analysis salvata", "toast.stored_removed":"Chiave salvata rimossa", "toast.remove_key_failed":"Impossibile rimuovere la chiave: {msg}", "toast.aa_refreshed":"Punteggi di Artificial Analysis aggiornati", "toast.refresh_failed":"Aggiornamento non riuscito: {msg}", "toast.load_profiles_failed":"Impossibile caricare i profili: {msg}", "toast.duplicated":"{name} duplicato", "toast.now_default":"{name} ora è quello predefinito", "toast.deleted":"{name} eliminato", "toast.default_reassigned":" — il predefinito ora è auto", "toast.saved_profile":"{name} salvato", "toast.file_too_large":"Il file è troppo grande per essere un’esportazione di profilo.", "toast.load_integrations_failed":"Impossibile caricare le integrazioni: {msg}", "toast.load_mi_failed":"Impossibile caricare le fonti dati: {msg}", "toast.source_added":"Fonte aggiunta", "toast.legacy_removed":"Voce legacy \"__custom__\" rimossa", "toast.saved_as":"Salvato {name} come {slug}. Recupera i suoi modelli qui sotto.", "confirm.remove_provider":"Rimuovere la chiave di {name}? Le richieste instradate a {name} inizieranno a fallire.", "confirm.remove_model":"Rimuovere il modello {name}?", "confirm.remove_custom":"Rimuovere il provider \"{name}\" e i suoi modelli?", "confirm.sign_out_others":"Disconnettere tutti gli altri browser di questo amministratore?", "confirm.reset_score":"Reimpostare {name} al suo punteggio AA?", "confirm.remove_aa_key":"Rimuovere la chiave Artificial Analysis salvata? Una chiave d’ambiente subentra di nuovo, se presente.", "confirm.change_slug":"Cambiare l’identificatore API da \"{old}\" a \"{new}\"?\n\nOgni client che invia model: \"{old}\" smetterà di funzionare.", "confirm.delete_source":"Eliminare questa fonte di metadati?", "confirm.legacy_remove":"Rimuovere definitivamente la chiave provider legacy \"__custom__\" ({prefix})?\n\nNon è usata per l’instradamento. Conserva la chiave altrove se ancora necessaria — non è recuperabile.", "confirm.revoke":"Revocare \"{name}\"?\n\nI client che usano questa chiave ricevono subito 401. Irreversibile — emetti una nuova chiave se serve di nuovo.", "confirm.rotate":"Ruotare \"{name}\"?\n\nViene creata una chiave sostitutiva con le stesse restrizioni e mostrata una sola volta.\n\nOK = revoca ora la vecchia chiave (cambio immediato).\nAnnulla = mantieni la vecchia chiave finché non la revochi tu.", "prompt.rename_key":"Rinomina la chiave \"{name}\" in:", "prompt.set_score":"Imposta punteggio di qualità manuale per {name} (0-100):", "prompt.aa_current":"Il punteggio AA attuale è: {score}", "prompt.override_note":"Nota facoltativa (perché sostituisci?):", "auth.session_expired":"La sessione è scaduta. Accedi di nuovo.", "auth.enter_creds":"Inserisci nome utente e password.", "auth.creds_required":"Nome utente e password sono obbligatori.", "auth.pw_mismatch":"Le password non coincidono.", "auth.paste_token":"Incolla il token di configurazione monouso dal log del server.", "auth.signed_out":"Disconnesso.", "auth.pw_match":"Le password coincidono.", "auth.pw_mismatch_yet":"Le password non coincidono ancora.", "auth.new_pw_mismatch":"Le nuove password non coincidono.", "auth.fill_three":"Compila tutti e tre i campi.", "qa.connection":"Connessione Artificial Analysis", "qa.test":"Testa connessione", "qa.replace":"Sostituisci chiave", "qa.add":"Aggiungi chiave", "qa.remove":"Rimuovi chiave", "qa.last_sync":"Ultima sincronizzazione riuscita", "qa.last_error":"Ultimo errore", "qa.never":"mai sincronizzato", "qa.from_env":"dall'ambiente", "qa.saving":"Salvataggio…", "qa.key_hint":"Crittografata su questo server e mai più mostrata. La chiave precedente resta attiva finché non salvi questa.", "qa.daily_limit_label":"Limite giornaliero della chiave", "qa.daily_limit_hint":"Richieste per 24 ore, come da pagina account Artificial Analysis. Lascia vuoto per il limite documentato di 100/giorno.", "qa.status.not_configured":"Non configurata", "qa.status.connected":"Connessa", "qa.status.invalid_key":"Chiave non valida", "qa.status.rate_limited":"Limite raggiunto", "qa.status.connection_failed":"Connessione fallita", "qa.status.cached":"Dati in cache", "pricing.legend":"Prezzi", "pricing.allow_estimates":"Consenti stime di riferimento in Auto, Più economico e limiti di costo", "pricing.allow_estimates_help":"Disattivato per impostazione predefinita. Si confrontano solo i prezzi confermati del provider; i modelli con solo una stima di riferimento restano esclusi da Auto. Se attivo, ogni decisione basata su stime viene etichettata.", "confirm.bulk_remove_models":"Rimuovere {count} modello/i selezionato/i? Le richieste associate falliranno.", "nav.chat":"Messaggi", "tab.chat.title":"Messaggi", "tab.chat.sub":"Parla con i tuoi modelli distribuiti. Instradato, in cache e computato come il traffico SDK.", "ui.open_chat":"Apri la chat", "ui.open_chat_hint":"Chatta con i tuoi modelli distribuiti dal browser — stesso routing, cache e tracciamento dei costi del traffico SDK.", "chat.new":"Nuova chat", "chat.settings_title":"Impostazioni chat", "chat.default_title":"Nuova chat", "chat.clear_history":"Cancella cronologia…", "chat.conversations_aria":"Conversazioni", "chat.model_aria":"Modello", "chat.regenerate":"Rigenera risposta", "chat.empty_title":"Chiedi qualsiasi cosa.", "chat.empty_sub":"Le richieste passano dal motore — stesso routing, cache e tracciamento costi del traffico SDK.", "chat.input_placeholder":"Messaggio a GeekCubo…", "chat.send":"Invia", "chat.stop":"Ferma", "chat.system_prompt":"Prompt di sistema…", "chat.system_prompt_set":"Prompt di sistema ✓", "chat.system_ph":"Sei un assistente utile…", "chat.system_help":"Vuoto = usa il valore predefinito della chat. Salvato per conversazione.", "chat.save_prompt":"Salva prompt", "chat.default_model":"Modello predefinito", "chat.default_model_help":"Usato per le nuove conversazioni. Il selettore della conversazione ha la precedenza.", "chat.temperature":"Temperatura", "chat.max_tokens":"Token di output max", "chat.default_system_prompt":"Prompt di sistema predefinito", "chat.default_system_prompt_ph":"Sei un assistente tecnico conciso.", "chat.default_system_help":"Si applica alle conversazioni senza prompt proprio.", "chat.save_history":"Salva la cronologia chat su questo server", "chat.retention_days":"Conserva le conversazioni per (giorni)", "chat.retention_help":"Le conversazioni più vecchie vengono rimosse. Vuoto = conserva tutto.", "chat.font_size":"Dimensione testo messaggi", "chat.fs_small":"Piccolo", "chat.fs_medium":"Medio", "chat.fs_large":"Grande", "chat.enter_to_send":"Invio manda il messaggio", "chat.privacy_note":"Le conversazioni restano nel database di questo server. Le richieste vanno ai provider configurati, esattamente come il traffico SDK.", "chat.privacy_ack":"Capisco che il traffico chat va ai provider configurati", "chat.save_settings":"Salva impostazioni", "chat.model_auto":"Auto (sceglie il router)", "chat.no_conversations":"Nessuna conversazione ancora.", "chat.delete_convo_title":"Elimina questa conversazione", "chat.kbd_enter_send":"Invio per inviare · Maiusc+Invio per una nuova riga", "chat.kbd_ctrl_enter_send":"Ctrl+Invio per inviare · Invio per una nuova riga", "chat.tokens_meta":"{in} ingresso · {out} uscita", "chat.error_note":"La generazione si è interrotta prima del completamento.", "chat.upstream_error":"Il modello upstream ha restituito un errore.", "toast.chat_load_failed":"Impossibile caricare i dati della chat: {msg}", "toast.chat_failed":"Richiesta di chat non riuscita: {msg}", "toast.chat_convo_deleted":"Conversazione eliminata", "toast.chat_cleared":"Cancellate {count} conversazioni", "toast.chat_temp_range":"La temperatura deve essere tra 0 e 2", "toast.chat_settings_saved":"Impostazioni chat salvate", "toast.chat_open_convo":"Apri prima una conversazione", "toast.chat_saved_prompt":"Prompt di sistema salvato per questa conversazione", "confirm.delete_conversation":"Eliminare questa conversazione?\n\nI messaggi vengono rimossi dal database del server. I record di utilizzo e costi restano nelle analisi.", "confirm.clear_chat_history":"Eliminare TUTTE le conversazioni salvate?\n\nTutti i messaggi di chat memorizzati su questo server vengono rimossi. I record di utilizzo e costi restano nelle analisi.", "q.ov_score":"Punteggio manuale (0–100)", "q.ov_note":"Nota", "q.ov_model_ph":"es. openai/gpt-4o, anthropic/claude-…", "q.ov_note_ph":"Perché sostituisce il punteggio AA", "q.ov_apply":"Applica sostituzione", "q.ov_clear":"Rimuovi sostituzione", "q.ov_help":"Uno o più id di modello, separati da virgole — la sostituzione si applica a ogni modello elencato. I punteggi manuali vincono sempre sui punteggi AA.", "toast.q_ids_required":"Inserisci almeno un id di modello", "toast.q_too_many":"L'operazione bulk è limitata a 500 id di modello", "toast.q_bulk_set":"Sostituzione impostata per {count} modello/i", "toast.q_bulk_clear":"Sostituzioni rimosse per {count} modello/i", "providers.bulk_actions":"Azioni di gruppo sui modelli", "providers.select_all":"Seleziona tutto", "providers.selected_count":"{count} selezionati", "providers.bulk_capability":"Capacità", "providers.bulk_capability_state":"Stato della capacità", "providers.cap_tools":"Strumenti", "providers.cap_vision":"Visione", "providers.cap_supported":"Supportato", "providers.cap_unsupported":"Non supportato", "providers.cap_unknown":"Sconosciuto", "providers.cap_catalog":"Usa catalogo", "providers.cap_json_mode":"Modalità JSON", "providers.cap_json_schema":"Schema JSON", "providers.apply":"Applica", "providers.enable":"Attiva", "providers.disable":"Disattiva", "providers.remove_selected":"Rimuovi selezionati", "providers.resolve_metadata":"Risolvi", "toast.metadata_resolved":"Metadati: {resolved} risolti, {ambiguous} ambigui, {unmatched} senza corrispondenza, {failed} errori.", "select.search_ph":"Cerca chiavi di catalogo…", "providers.catalog_key_ph":"Cerca chiavi di catalogo…", "select.remove_item":"Rimuovi {name}", "select.use_custom":"Usa \"{name}\"", "select.no_matches":"Nessun modello corrispondente", "select.more_results":"Altri {count}: continua a digitare per restringere", "q.ov_model_search_ph":"Cerca e scegli i modelli…", "q.ov_help_picker":"Cerca e scegli uno o più modelli, oppure seleziona le righe nella tabella sotto. I punteggi manuali prevalgono sempre su quelli AA.", "q.filter_ph":"Filtra modelli…", "q.select_filtered":"Seleziona filtrati", "q.select_all_filtered":"Seleziona tutti i modelli filtrati", "q.deselect_all":"Deseleziona tutto", "q.bulk_set":"Imposta punteggio ai selezionati", "q.bulk_clear":"Cancella override selezionati", "q.select_model":"Seleziona {name}", "confirm.q_bulk_clear":"Cancellare gli override manuali di {count} modelli selezionati?", "qa.daily_limit_short":"Limite giornaliero", "chat.attach":"Allega file", "chat.attach_drop":"Trascina i file per allegarli", "chat.attach_remove":"Rimuovi allegato", "chat.attach_unreadable":"Impossibile leggere questo file; viene inviato solo il nome.", "chat.attach_uploading":"Caricamento…", "chat.attach_too_large":"Troppo grande (max {max} MB)", "toast.chat_attach_failed":"Impossibile allegare {name}: {msg}", "toast.chat_attach_disabled":"Gli allegati sono disattivati su questo server.", "toast.chat_attach_too_many":"Al massimo {max} allegati per messaggio.", "toast.chat_attach_extract_failed":"{name}: impossibile leggerlo ({msg})", "toast.chat_attach_wait":"Attendi il completamento dei caricamenti.", "chat.search_toggle":"Ricerca web", "chat.search_settings":"Ricerca web", "chat.search_help":"Se attiva, GeekCubo cerca sul web prima di rispondere e cita le pagine usate. I risultati vengono inseriti come messaggio di sistema, così qualsiasi modello può usarli.", "chat.search_mode":"Modalità di ricerca", "chat.search_mode_off":"Disattivata", "chat.search_mode_manual":"Manuale (per messaggio)", "chat.search_mode_auto":"Automatica (riservata)", "chat.search_mode_help":"La modalità manuale mostra un interruttore nel compositore. Quella automatica è riservata e non ancora implementata.", "chat.search_backend":"Motore di ricerca", "chat.search_backend_none":"Scegli un motore…", "chat.search_backend_searxng":"SearXNG (auto-ospitato)", "chat.search_backend_brave":"API Brave Search", "chat.search_backend_tavily":"Tavily", "chat.search_url":"URL SearXNG", "chat.search_url_ph":"http://searxng:8080/", "chat.search_url_help":"URL di base della tua istanza SearXNG. Il profilo search dell'installer la espone sulla rete interna.", "chat.search_api_key":"Chiave API", "chat.search_api_key_ph":"Incolla una nuova chiave per sostituire quella salvata", "chat.search_key_clear":"Rimuovi chiave salvata", "chat.search_key_help":"Salvata cifrata su questo server e mai più mostrata. Brave e Tavily richiedono una chiave; SearXNG no.", "chat.search_max_searches":"Ricerche massime per conversazione", "chat.search_max_results":"Risultati per ricerca", "chat.search_max_fetches":"Pagine da scaricare per ricerca", "chat.search_timeout":"Timeout ricerca (secondi)", "chat.search_test":"Verifica connessione", "chat.search_testing":"Verifica in corso…", "chat.search_test_ok":"{count} risultati in {ms} ms", "chat.search_test_failed":"Verifica della ricerca non riuscita: {msg}", "chat.search_key_state_unset":"Nessuna chiave salvata", "chat.search_key_state_set":"Chiave salvata", "chat.search_key_state_undecryptable":"Impossibile decifrare la chiave salvata", "chat.context_budget":"Contesto: {tokens} / {budget} token", "chat.context_omitted":"{count} messaggi precedenti omessi", "chat.sources":"Fonti", "chat.search_used":"ricerca web: {backend}", "toast.search_saved":"Impostazioni di ricerca web salvate", "toast.search_save_failed":"Impossibile salvare le impostazioni di ricerca: {msg}", "toast.search_test_failed":"Verifica della ricerca web non riuscita", "nav.local":"IA locale", "tab.local.title":"IA locale", "tab.local.sub":"Servi modelli dalle tue macchine attraverso questo router.", "local.title":"Connessione IA locale", "local.sub":"Instrada verso modelli in esecuzione sulle tue macchine. Un piccolo connettore si collega a questo server, quindi non si aprono porte e non serve alcun tunnel in ingresso.", "local.refresh":"Aggiorna", "local.setup_button":"Configura una macchina", "local.feature_off_title":"La connessione IA locale è disattivata sul server", "local.feature_off_body":"Imposta LOCAL_CONNECT_ENABLED=true nell'ambiente del server e riavvia, poi ricarica questa pagina.", "local.url_missing_title":"Nessun URL pubblico configurato", "local.url_missing_body":"Imposta LOCAL_CONNECT_PUBLIC_URL con l'indirizzo a cui i connettori devono collegarsi (ad esempio https://example.com) così il comando di installazione e i file di servizio vengono compilati.", "local.settings_title":"Comportamento del routing", "local.settings_sub":"Stabilisce se i modelli locali partecipano ad Auto e se una richiesta può ripiegare sul cloud.", "local.set_enabled":"Consenti le macchine locali per il routing", "local.set_auto":"Includi i modelli locali nella selezione automatica", "local.set_no_fallback":"Non ripiegare mai sul cloud quando un modello locale fallisce", "local.settings_help":"I modelli locali sono considerati per Auto solo se il prezzo è zero confermato e la macchina è approvata e in linea. Con \"non ripiegare mai\" attivo, una richiesta solo locale fallisce invece di essere servita da un provider cloud.", "local.save_settings":"Salva", "local.settings_saved":"Impostazioni di routing locale salvate.", "local.machines_title":"Macchine", "local.machines_sub":"Ogni macchina è un connettore. Le macchine in attesa sono visibili ma non ricevono traffico finché non le approvi.", "local.machines_empty":"Nessuna macchina. Usa \"Configura una macchina\" per generare un codice di registrazione.", "local.enrollments_title":"Codici di registrazione", "local.enrollments_sub":"Codici monouso che consentono a un connettore di registrarsi. Ogni codice viene consumato alla prima connessione di una macchina.", "local.new_code":"Nuovo codice", "local.install_title":"Installa il connettore", "local.install_sub":"Esegui questo sulla macchina che ospita i tuoi modelli (Ollama, LM Studio, vLLM, llama.cpp o qualsiasi server compatibile [OI]).", "local.service_files":"Eseguilo come servizio", "local.delete":"Elimina", "local.never":"mai", "local.ctx_suffix":"contesto", "local.ctx_unknown":"contesto sconosciuto", "local.no_models":"Questa macchina non ha ancora segnalato alcun modello.", "local.no_enrollments":"Nessun codice di registrazione.", "local.enroll_active":"Attivo", "local.enroll_used":"Usato", "local.status_online":"In linea", "local.status_offline":"Non in linea", "local.status_pending":"In attesa di approvazione", "local.status_approved":"Approvata", "local.status_revoked":"Revocata", "local.pending_note":"Questa macchina attende l'approvazione. I modelli sono elencati ma non riceveranno traffico.", "local.action_approve":"Approva", "local.action_discover":"Rileva modelli", "local.action_revoke":"Revoca", "local.action_rotate":"Ruota credenziale", "local.action_delete":"Elimina", "local.meta_host":"Nome host", "local.meta_platform":"Piattaforma", "local.meta_agent":"Versione del connettore", "local.meta_adapters":"Adattatori", "local.meta_seen":"Ultimo accesso", "local.col_model":"Modello", "local.col_adapter":"Tipo di adattatore", "local.col_context":"Contesto", "local.col_caps":"Capacità", "local.col_enabled":"Attivo", "local.kpi_machines":"Macchine", "local.kpi_online":"In linea ora", "local.kpi_pending":"In attesa di approvazione", "local.kpi_models":"Modelli", "local.toast_approved":"Macchina approvata.", "local.toast_revoked":"Macchina revocata.", "local.toast_deleted":"Macchina eliminata.", "local.toast_discovered":"Elenco modelli aggiornato.", "local.confirm_revoke":"Revocare questa macchina? Il suo connettore viene disconnesso subito e non potrà riconnettersi finché non ruoti la credenziale.", "local.confirm_delete_machine":"Eliminare questa macchina e il suo elenco di modelli? L'operazione non può essere annullata.", "local.confirm_rotate":"Ruotare la credenziale di questa macchina? Il connettore in esecuzione continua fino alla riconnessione, poi la vecchia credenziale viene rifiutata.", "local.confirm_delete_enrollment":"Eliminare questo codice di registrazione?", "local.credential_once_title":"Copia subito la nuova credenziale", "local.credential_once_body":"Viene mostrata una sola volta. Salvala nella configurazione del connettore sulla macchina.", "local.wizard_title":"Connetti una macchina locale", "local.wizard_close":"Chiudi", "local.wizard_back":"Indietro", "local.wizard_next":"Avanti", "local.wizard_done":"Fatto", "local.step1":"Abilita", "local.step2":"Codice di registrazione", "local.step3":"Installa", "local.step4":"Registra", "local.step5":"Avvia", "local.step6":"Approva", "local.step7":"Modelli", "local.step8":"Routing automatico", "local.w0_title":"Attiva la funzione", "local.w0_body":"La connessione IA locale è una funzione lato server. Deve essere abilitata prima che i connettori possano registrarsi.", "local.w0_ready":"La funzione è abilitata. Continua per creare un codice di registrazione.", "local.w0_blocked":"La funzione è disabilitata su questo server. Imposta LOCAL_CONNECT_ENABLED=true e riavvia, poi ricarica questa pagina.", "local.w1_title":"Crea un codice di registrazione", "local.w1_body":"Un codice monouso autorizza un singolo connettore a registrarsi. Scade dopo un breve periodo.", "local.w1_name":"Nome della macchina (facoltativo)", "local.w1_name_ph":"es. ufficio-gpu", "local.w1_name_help":"Un'etichetta per riconoscere questa macchina nell'elenco. Puoi rinominarla in seguito.", "local.w1_created":"Codice di registrazione creato", "local.w2_title":"Installa il pacchetto del connettore", "local.w2_body":"Sulla macchina che ospita i tuoi modelli, installa il connettore. È richiesto Python 3.11 o successivo.", "local.w2_note":"Installalo in un ambiente virtuale per isolarlo dai pacchetti di sistema.", "local.w3_title":"Registra la macchina", "local.w3_body":"Esegui il comando di registrazione con il codice del passo 2. La credenziale viene scritta nel file di configurazione del connettore.", "local.w3_note":"Il codice è monouso. Se è scaduto, creane uno nuovo.", "local.w4_title":"Avvia il connettore", "local.w4_body":"Esegui il connettore in primo piano per vederlo collegarsi, poi spostalo in un servizio.", "local.w4_note":"Il connettore mantiene aperta una singola WebSocket in uscita e si riconnette automaticamente.", "local.w5_title":"Attendi che compaia la macchina", "local.w5_body":"Quando il connettore si collega, la macchina appare qui. Aggiorna se richiede un momento.", "local.w5_seen":"{name} si è collegata.", "local.w5_waiting":"Nessuna macchina si è ancora collegata.", "local.w5_recheck":"Controlla di nuovo", "local.w6_title":"Approva la macchina", "local.w6_body":"Una nuova macchina resta in attesa finché un amministratore non la approva. Fino ad allora non le viene instradato nulla.", "local.w6_none":"Non c'è ancora nessuna macchina da approvare.", "local.w6_must_approve":"Approva la macchina in attesa prima di continuare.", "local.w7_title":"Abilita i modelli locali in Auto", "local.w7_body":"Attiva \"Includi i modelli locali nella selezione automatica\" e abilita i modelli a cui vuoi instradare. I modelli locali vengono scelti per Auto solo quando il prezzo è zero confermato.", "local.w7_done":"Configurazione completata. I modelli locali ora compaiono nelle pagine Provider e Routing." },
  ar: { "q.tabs_label":"أقسام الجودة", "q.tab_models":"النماذج", "q.tab_scores":"درجات الجودة", "q.tab_aa":"اتصال Artificial Analysis", "q.col_availability":"التوفر", "q.avail_yes":"متاح", "q.avail_no":"لا يوجد مفتاح مزوّد", "q.avail_no_title":"لا يوجد مفتاح مزوّد مُعدّ يخدم هذا النموذج. بيانات القياس وحدها لا تجعل النموذج قابلاً للنشر.", "q.sync_title":"مزامنة القياسات", "q.sync_last_ok":"آخر مزامنة ناجحة", "q.sync_last_attempt":"أحدث محاولة", "q.sync_returned":"النماذج التي أعادها AA", "q.sync_matched":"مطابقة للكتالوج", "q.sync_unmatched":"غير مطابقة", "q.sync_overrides":"الدرجات اليدوية", "q.sync_outcome_ok":"نجحت", "q.sync_outcome_failed":"فشلت", "q.sync_need_key":"أضف مفتاحًا في تبويب Artificial Analysis لمزامنة درجات القياس. الدرجات اليدوية تعمل دون مفتاح.", "q.sync_never":"لم تتم أي مزامنة بهذا المفتاح بعد. استخدم التحديث من AA.", "q.sync_no_models":"لم تُرجع آخر مزامنة أي نماذج.", "q.status_line":"{matched} نموذجًا ببيانات قياس · {overrides} درجة يدوية", "q.src.live":"مباشر", "q.src.stale_cache":"مخزّن مؤقتًا (تعذّر الوصول إلى AA)", "q.src.stale_db":"مخزّن مؤقتًا (لقطة محفوظة)", "q.src.error":"فشلت المزامنة", "q.src.missing_key":"لا يوجد مفتاح API", "q.auto_status":"حالة التوجيه التلقائي", "q.auto_status_hint":"ما سيختاره model=\"auto\" الآن. يعتمد على المزوّدين المُعدّين، لا على مزامنة القياسات.", "q.auto_no_provider":"لا يوجد نموذج قابل للنشر يلبي المتطلبات الحالية. أضف مفتاحًا في صفحة المزوّدين. هذا منفصل عن مزامنة Artificial Analysis.", "qa.credential":"مفتاح API", "qa.cred_stored":"محفوظ على هذا الخادم (مشفّر)", "qa.cred_env":"من بيئة الخادم", "qa.last_test":"آخر اختبار اتصال", "qa.last_test_ok":"آخر اختبار ناجح", "qa.not_tested":"لم يُختبر بعد", "qa.sync_status":"مزامنة القياسات", "qa.tier":"خطة {tier}", "qa.troubleshooting":"استكشاف أخطاء الاتصال", "qa.status.key_configured":"تم إعداد المفتاح", "qa.sync.not_configured":"غير مُعدّ", "qa.sync.never_synced":"لم تتم المزامنة", "qa.sync.synced":"تمت المزامنة", "qa.sync.sync_failed":"فشلت المزامنة", "qa.err.invalid_key":"مفتاح غير صالح", "qa.err.insufficient_tier":"الخطة لا تتضمن نقطة النهاية", "qa.err.endpoint_retired":"نقطة النهاية متوقفة", "qa.err.rate_limited":"تم بلوغ حد الطلبات", "qa.err.timeout":"انتهت المهلة", "qa.err.malformed_response":"استجابة غير متوقعة", "qa.err.no_data":"لم تُرجَع نماذج", "qa.err.no_catalog_match":"لا تطابق مع الكتالوج", "qa.err.server_error":"خطأ في خادم AA", "qa.err.connection_failed":"فشل الاتصال", "auth.tagline":"بوابة واحدة. كل نماذج الذكاء الاصطناعي.", "auth.welcome":"مرحبًا بعودتك", "auth.subtitle":"سجّل الدخول إلى وحدة تحكم المسؤول لهذا التنصيب من GeekCubo.", "auth.api_key":"مفتاح API", "auth.continue":"متابعة", "nav.search":"بحث", "nav.overview":"نظرة عامة", "nav.providers":"المزوّدون", "nav.routing":"توجيه الطلبات", "nav.analytics":"التحليلات", "nav.api_keys":"مفاتيح API", "nav.help_docs":"المساعدة والوثائق", "nav.sign_out":"تسجيل الخروج", "status.connected":"متصل", "status.disconnected":"غير متصل", "auth.checking":"جارٍ التحقق…", "auth.welcome_aboard":"مرحبًا بك.", "auth.key_invalid":"هذا المفتاح لم يعمل. تحقّق من البادئة sk-geek-…", "tab.overview.title":"نظرة عامة", "tab.overview.sub":"موجّه LLM أحادي المستأجر بنظرة سريعة.", "tab.providers.title":"مفاتيح المزوّدين", "tab.providers.sub":"BYOK — مشفّرة أثناء التخزين وتُستخدم لاستدعاء نماذج LLM الخارجية.", "tab.routing.title":"التوجيه", "tab.routing.sub":"كيف يختار model='auto' النموذج المناسب لكل طلب.", "tab.analytics.title":"التحليلات", "tab.analytics.sub":"الإنفاق والزمن والسجل المحلي للطلبات فقط.", "tab.keys.title":"مفاتيح API", "tab.keys.sub":"مفاتيح sk-geek-* التي تصادق على حركة الاستدلال من SDK وCLI.", "nav.quality":"الجودة", "tab.quality.title":"درجات الجودة", "tab.quality.sub":"درجات اختبار أداء حقيقية لاستراتيجية التوجيه حسب الجودة، مصدرها Artificial Analysis.", "auth.username":"اسم المستخدم", "auth.password":"كلمة المرور", "auth.sign_in":"تسجيل الدخول", "nav.security":"الأمان", "tab.security.title":"الأمان", "tab.security.sub":"حساب المسؤول وكلمة المرور والجلسات.", "tab.profiles.title":"ملفات التوجيه", "tab.profiles.sub":"إعدادات Auto مسمّاة يختارها العملاء عبر معرّف النموذج.", "tab.integrations.title":"اربط أداة", "tab.integrations.sub":"إعداد جاهز لـ OpenCode وClaude Code وCursor وغيرها.", "tab.intelligence.title":"بيانات النماذج", "tab.intelligence.sub":"مصدر أسعار النماذج وحدودها.", "auth.loading":"جارٍ التحميل…", "auth.checking_status":"جارٍ التحقق من حالة المسؤول.", "auth.signin_title":"تسجيل الدخول", "auth.signin_sub":"وصول المسؤول إلى تنصيب GeekCubo هذا.", "auth.forgot":"هل نسيت كلمة المرور؟", "auth.reset_hint":"أعد تعيينها على المضيف أو الحاوية:", "auth.reset_note":"المفاتيح والمزوّدون والاستخدام غير متأثرة.", "auth.setup_title":"إنشاء حساب مسؤول", "auth.setup_sub":"يدير تنصيب GeekCubo هذا: بيانات المزوّدين ومفاتيح API والتوجيه.", "auth.min_password":"٨ أحرف على الأقل", "auth.confirm_password":"تأكيد كلمة المرور", "auth.setup_token":"رمز الإعداد", "auth.from_log":"من سجل الخادم", "auth.create_admin":"إنشاء المسؤول", "auth.where_token":"أين رمز الإعداد؟", "auth.token_hint":"يُطبع في سجل الخادم عند أول تشغيل. لإصدار رمز جديد:", "auth.toggle_password":"إظهار كلمة المرور أو إخفاؤها", "ov.spend":"الإنفاق (٧ أيام)", "ov.savings":"وفر التوجيه", "ov.p50":"زمن استجابة p50", "ov.models":"النماذج القابلة للنشر", "ov.quickstart":"بداية سريعة", "ov.recent":"النشاط الأخير", "prov.title":"مفاتيح المزوّدين", "prov.tab_std":"مزوّدون قياسيون", "prov.tab_custom":"مزوّدون مخصّصون", "routing.strategy":"استراتيجية التوجيه", "routing.pools":"مجموعات النماذج", "routing.advanced":"الاحتياطي والتصعيد والاستمرارية", "routing.explain":"اختبر قرار توجيه", "profiles.title":"ملفات التوجيه", "int.title":"اربط أداة الذكاء الاصطناعي", "md.title":"مصادر بيانات النماذج", "md.lookup":"البحث عن السعر", "an.spend":"الإنفاق حسب النموذج", "an.latency":"زمن الاستجابة حسب المزوّد", "an.recent":"الطلبات الأخيرة", "keys.title":"مفاتيح API للموجّه", "sec.sessions":"الجلسات", "q.setup":"إعداد تقييم الجودة", "q.models":"النماذج", "preset.heading":"ابدأ من قالب", "preset.sub":"تفتح القوالب المحرّر مُعبّأً مسبقًا — عدّل ما تشاء قبل الحفظ.", "preset.economy":"أرخص نموذج قادر على كل طلب. أقل إنفاق، دون حد أدنى للجودة.", "preset.premium":"أقوى النماذج أولًا دون النظر إلى السعر. للأعمال التي تغلب فيها الجودة.", "preset.coding":"تذهب استدعاءات الأدوات والطلبات الطويلة إلى مجموعة Hard. لأعمال الوكلاء والمحرّرات.", "preset.fast":"توجيه متوازن يفضّل زمن استجابة أقل داخل المجموعة.", "ui.profiles":"الملفات الشخصية", "ui.security":"الأمان", "ui.api_keys":"مفاتيح API", "ui.connect_a_tool":"اربط أداة", "ui.model_data":"بيانات النماذج", "ui.connecting":"جارٍ الاتصال…", "ui.language":"اللغة", "ui.light":"فاتح", "ui.system":"النظام", "ui.dark":"داكن", "ui.openai_compatible_base_url":"عنوان أساسي متوافق مع OpenAI", "ui.copy":"نسخ", "ui.use_this_in_any_openai_compatible_client":"استخدمه في أي عميل متوافق مع OpenAI.", "ui.signed_in":"تم تسجيل الدخول", "ui.security_and_sessions":"الأمان والجلسات", "ui.api_keys_2":"مفاتيح API", "ui.sign_out":"تسجيل الخروج", "ui.you_re_up_point_any_openai_sdk_at_your_b":"كل شيء جاهز — وجّه أي SDK من OpenAI إلى عنوانك الأساسي.", "ui.last_5_requests_routed_through_this_serv":"آخر ٥ طلبات مرّت عبر هذا الخادم.", "ui.view_all":"عرض الكل", "ui.no_requests_yet":"لا توجد طلبات بعد.", "ui.new_here_get_fully_set_up_in_2_minutes":"أول مرة؟ أكمل الإعداد في دقيقتين", "ui.re_enter_as_a_named_provider":"أعد إدخاله كمزوّد مسمّى", "ui.remove_legacy_entry":"إزالة الإدخال القديم", "ui.provider":"المزوّد", "ui.others_openai_format":"أخرى (تنسيق OpenAI)", "ui.api_key":"مفتاح API", "ui.provider_name":"اسم المزوّد", "ui.display_name_a_unique_internal_slug_is_d":"الاسم المعروض. يُشتق منه معرّف داخلي فريد تلقائيًا.", "ui.api_base_url":"عنوان API الأساسي", "ui.usually_ends_in_v1_must_be_https_unless_":"ينتهي عادةً بـ /v1. يجب أن يكون https ما لم يكن المضيف في CUSTOM_PROVIDER_ALLOWED_LOCAL_HOSTS.", "ui.api_key_2":"مفتاح API", "ui.encrypted_at_rest_never_displayed_again_":"مشفّر أثناء التخزين. لا يُعرض مرة أخرى بعد الحفظ.", "ui.prefix":"البادئة", "ui.status":"الحالة", "ui.no_provider_keys_yet":"لا توجد مفاتيح مزوّدين بعد", "ui.add_at_least_one_to_start_routing_real_t":"أضف واحدًا على الأقل لبدء توجيه حركة حقيقية. اختر مزوّدًا أعلاه أو انقر إضافة سريعة.", "ui.lowest_cost_that_clears_your_quality_flo":"أقل تكلفة تتجاوز حد الجودة لديك. خيار آمن مع أي عدد من المزوّدين.", "ui.recommended":"موصى به", "ui.lowest_per_token_cost_meeting_the_reques":"أقل تكلفة لكل رمز مع تلبية متطلبات الطلب. قد تختلف جودة المخرجات.", "ui.highest_score_from_artificial_analysis_o":"أعلى درجة من Artificial Analysis أو من تجاوزاتك اليدوية. بدون درجات يستخدم السعر كتقدير تقريبي.", "ui.re_ranks_by_observed_success_rate_and_la":"يعيد الترتيب حسب معدل النجاح وزمن الاستجابة الملاحظين بعد أن يجمع كل نموذج ٢٠+ طلبًا هنا. حتى ذلك الحين: متوازن.", "ui.sends_each_request_to_your_mundane_or_ha":"يرسل كل طلب إلى مجموعة Mundane أو Hard بناءً على إشارات قابلة للملاحظة (الأدوات، الحجم، الطول).", "ui.highest_throughput_and_lowest_first_toke":"أعلى إنتاجية وأقل زمن لاستجابة أول رمز وفق بيانات القياس. محتفظ به لتوافق الإعدادات القائمة.", "ui.legacy":"قديم", "ui.registered_models":"النماذج المسجّلة", "ui.show":"عرض", "ui.deployable":"قابلة للنشر", "ui.custom_providers":"مزوّدون مخصّصون", "ui.model":"النموذج", "ui.capabilities":"الإمكانات", "ui.context":"السياق", "ui.price_1m_in_out":"السعر /1M (إدخال · إخراج)", "ui.availability":"التوفّر", "ui.pools":"المجموعات", "ui.previous":"السابق", "ui.next":"التالي", "ui.fallback_and_escalation_always_keep_the_":"الاحتياطي والتصعيد يحافظان دائمًا على الإمكانات المطلوبة للطلب. تُتخذ القرارات قبل بدء الطلب، ولا يتغيّر النموذج أبدًا في منتصف البث.", "ui.maximum_attempts_primary_fallbacks":"أقصى عدد محاولات (الأساسي + الاحتياطية)", "ui.what_counts_as_retryable":"ما الذي يُعاد المحاولة فيه", "ui.quality_floor_percentile_0_off":"حد الجودة (المئين، 0 = إيقاف)", "ui.needs_quality_scores_ignored_and_reporte":"يحتاج درجات جودة؛ يُتجاهل (ويُبلّغ عنه) عند عدم وجودها.", "ui.what_the_quality_floor_does":"ما يفعله حد الجودة", "ui.balanced_weighs_price_against_quality_th":"«متوازن» يوازن بين السعر والجودة. يستبعد الحد النماذج التي تقل عن ذلك المئين، فلا يمكن لنموذج رخيص جدًا وضعيف أن يفوز. اضبطه على 0 لإيقاف الحد تمامًا.", "ui.messages":"الرسائل ≥", "ui.prompt_characters":"أحرف الطلب ≥", "ui.how_request_signals_are_measured":"كيف تُقاس إشارات الطلب", "ui.mode":"الوضع", "ui.off":"إيقاف", "ui.manual_client_sends_x_geek_escalate":"يدوي (العميل يرسل x-geek-escalate)", "ui.auto_after_repeated_upstream_failures":"تلقائي (بعد تكرار فشل المزوّد)", "ui.failures_before_escalating":"عدد مرات الفشل قبل التصعيد", "ui.max_escalations_per_conversation":"أقصى عدد تصعيدات لكل محادثة", "ui.destination_pool":"المجموعة المستهدفة", "ui.when_escalation_triggers":"متى يُفعّل التصعيد", "ui.remember_for_minutes":"التذكّر لمدة (دقائق)", "ui.what_continuity_does":"ما تفعله الاستمرارية", "ui.save_routing_policy":"حفظ سياسة التوجيه", "ui.dry_run_shows_which_model_auto_would_cho":"محاكاة: تعرض النموذج الذي سيختاره Auto وسببه. لا يُرسل شيء إلى المزوّد.", "ui.messages_2":"الرسائل", "ui.prompt_chars":"أحرف الطلب", "ui.explain":"اشرح", "ui.three_filters_applied_in_order":"ثلاثة مرشّحات تُطبّق بالترتيب.", "ui.how_each_strategy_maps_to_litellm_router":"كيف تُقابل كل استراتيجية في LiteLLM Router", "ui.strategy":"الاستراتيجية", "ui.import_json":"استيراد JSON", "ui.new_profile":"ملف شخصي جديد", "ui.generates_configuration_that_points_a_cl":"ينشئ إعدادًا يوجّه عميلًا إلى GeekCubo هذا. تُشار إلى المفاتيح عبر متغيّر بيئة ولا تُضمَّن أبدًا.", "ui.search_tools":"بحث عن الأدوات", "ui.routing_profile_or_model":"ملف التوجيه أو النموذج", "ui.endpoint":"نقطة النهاية", "ui.format":"التنسيق", "ui.download":"تنزيل", "ui.add_source":"إضافة مصدر", "ui.name":"الاسم", "ui.https_url_models_dev_compatible_json":"عنوان HTTPS (JSON متوافق مع models.dev)", "ui.save_source":"حفظ المصدر", "ui.cancel":"إلغاء", "ui.shows_what_each_enabled_source_reports_f":"يعرض ما يبلّغ عنه كل مصدر مفعّل لهذا النموذج وأي قيمة سيستخدمها GeekCubo. أسعارك المضبوطة تفوز دائمًا.", "ui.look_up":"بحث", "ui.routing":"التوجيه", "ui.volume":"الحجم", "ui.routing_decisions":"قرارات التوجيه", "ui.how_auto_requests_were_classified_and_wh":"كيف صُنّفت طلبات Auto وإلى أين ذهبت.", "ui.by_tier":"حسب الطبقة", "ui.by_strategy":"حسب الاستراتيجية", "ui.by_routing_id":"حسب معرّف التوجيه", "ui.top_models_served":"النماذج الأكثر خدمة", "ui.reliability":"الموثوقية", "ui.errors_by_cause":"الأخطاء حسب السبب", "ui.compare_against_a_baseline_model":"قارن مع نموذج أساسي", "ui.none":"لا شيء", "ui.compare":"قارن", "ui.how_the_comparison_is_calculated":"كيف تُحسب المقارنة", "ui.p50_and_p99_sourced_from_local_request_l":"p50 و p99 — من سجلات الطلبات المحلية.", "ui.requests":"الطلبات", "ui.newest_first_click_a_row_to_copy_its_tra":"الأحدث أولًا. انقر على صف لنسخ معرّف التتبّع الخاص به.", "ui.when":"متى", "ui.tokens_in_out":"الرموز (إدخال / إخراج)", "ui.latency":"زمن الاستجابة", "ui.no_traffic_yet":"لا توجد حركة بعد", "ui.once_you_start_sending_requests_they_ll_":"بمجرد بدء إرسال الطلبات ستظهر هنا في الوقت الحقيقي.", "ui.expires":"ينتهي", "ui.never":"أبدًا", "ui.7_days":"٧ أيام", "ui.30_days":"٣٠ يومًا", "ui.90_days":"٩٠ يومًا", "ui.1_year":"سنة واحدة", "ui.use_it_with_opencode":"استخدمه مع OpenCode:", "ui.created":"أُنشئ", "ui.last_used":"آخر استخدام", "ui.actions":"الإجراءات", "ui.no_api_keys":"لا توجد مفاتيح API", "ui.generate_one_above_to_start_sending_requ":"أنشئ واحدًا أعلاه لبدء إرسال الطلبات من SDK أو CLI.", "ui.administrator":"المسؤول", "ui.the_single_local_account_that_controls_t":"الحساب المحلي الوحيد الذي يتحكم في هذا التنصيب.", "ui.password_was_reset_from_the_command_line":"أُعيد تعيين كلمة المرور من سطر الأوامر", "ui.change_password":"تغيير كلمة المرور", "ui.current_password":"كلمة المرور الحالية", "ui.new_password":"كلمة المرور الجديدة", "ui.confirm_new_password":"تأكيد كلمة المرور الجديدة", "ui.update_password":"تحديث كلمة المرور", "ui.signed_in_browsers_for_this_administrato":"المتصفحات المسجّلة لهذا المسؤول. تنتهي الجلسات بعد ١٢ ساعة أو ٦٠ دقيقة من الخمول.", "ui.log_out_all_other_sessions":"تسجيل الخروج من كل الجلسات الأخرى", "ui.device":"الجهاز", "ui.last_active":"آخر نشاط", "ui.local_recovery":"استعادة محلية", "ui.password_recovery_is_local_only_by_desig":"استعادة كلمة المرور محلية فقط بحكم التصميم — لا إعادة تعيين بالبريد ولا نقطة نهاية عامة يمكنها تغييرها.", "ui.open_a_shell_where_geekcubo_runs_host_or":"افتح صدفة حيث يعمل GeekCubo (المضيف أو الحاوية).", "ui.choose_a_new_password_at_the_prompt_all_":"اختر كلمة مرور جديدة عند المطالبة. تُسجَّل خروج كل جلسات اللوحة؛ مفاتيح API والمزوّدون وبيانات الاستخدام لا تتأثر.", "ui.artificial_analysis_api_key":"مفتاح API لـ Artificial Analysis", "ui.optional":"(اختياري)", "ui.save_key":"حفظ المفتاح", "ui.remove_stored_key":"إزالة المفتاح المحفوظ", "ui.how_quality_scoring_works":"كيف يعمل تقييم الجودة", "ui.paste_it_above_and_save_it_is_encrypted_":"الصقه أعلاه واحفظه. يُشفّر أثناء التخزين، وتُهمَل أي بيانات مخزّنة مؤقتًا ليستخدم التحديث التالي المفتاح الجديد.", "ui.quality_scores":"درجات الجودة", "ui.where_these_numbers_come_from":"من أين تأتي هذه الأرقام", "ui.manual":"يدوي", "ui.effective":"الفعلي", "ui.m_blended":"$/M مجمّع", "ui.help_and_docs":"المساعدة والوثائق", "ui.what_is_geekcubo":"ما هو GeekCubo؟", "ui.60_second_quickstart":"بداية سريعة في ٦٠ ثانية", "ui.keyboard_shortcuts":"اختصارات لوحة المفاتيح", "ui.switch_tabs":"تبديل التبويب", "ui.command_palette":"لوحة الأوامر", "ui.toggle_this_help":"إظهار أو إخفاء هذه المساعدة", "ui.close_drawers_palette":"إغلاق الأدراج / اللوحة", "ui.going_further":"إلى أبعد", "js.ov_empty_a":"لا توجد طلبات بعد.", "js.ov_empty_b":"بمجرد إرسال أول استدعاء سيظهر هنا.", "js.ra_unavailable":"تحليلات التوجيه غير متاحة.", "js.no_spend":"لا توجد مصروفات مسجّلة في هذه الفترة بعد.", "js.no_traffic":"لا توجد حركة بعد", "toast.copied":"تم النسخ إلى الحافظة", "toast.copy_blocked":"تعذّر النسخ — حظره المتصفح", "toast.signed_in":"تم تسجيل الدخول باسم {name}", "toast.admin_created":"أُنشئ المسؤول {name}", "toast.signed_out":"تم تسجيل الخروج", "toast.load_providers_failed":"تعذّر تحميل المزوّدين: {msg}", "toast.removed_provider":"تمت إزالة {name}", "toast.api_key_empty":"لا يمكن ترك مفتاح API فارغًا", "toast.saved_provider":"تم حفظ مفتاح {name}", "toast.load_custom_failed":"تعذّر تحميل المزوّدين المخصّصين: {msg}", "toast.updated":"تم تحديث {name}", "toast.model_id_empty":"لا يمكن ترك معرّف النموذج فارغًا", "toast.model_id_dup":"معرّف النموذج هذا مسجّل بالفعل", "toast.model_saved":"تم حفظ النموذج", "toast.select_one_model":"اختر نموذجًا جديدًا واحدًا على الأقل", "toast.added_models_one":"أُضيف نموذج واحد", "toast.added_models_many":"أُضيف {count} من النماذج", "toast.load_routing_failed":"تعذّر تحميل التوجيه: {msg}", "toast.routing_strategy":"استراتيجية التوجيه: {name}", "toast.policy_saved":"تم حفظ سياسة التوجيه", "toast.load_models_failed":"تعذّر تحميل النماذج: {msg}", "toast.load_analytics_failed":"تعذّر تحميل التحليلات: {msg}", "toast.load_keys_failed":"تعذّر تحميل المفاتيح: {msg}", "toast.revoked":"تم إلغاء {name}", "toast.name_empty":"لا يمكن ترك الاسم فارغًا", "toast.key_renamed":"تمت إعادة تسمية المفتاح", "toast.name_first":"أعطِ المفتاح اسمًا أولًا", "toast.created":"أُنشئ {name}", "toast.load_security_failed":"تعذّر تحميل إعدادات الأمان: {msg}", "toast.password_updated":"تم تحديث كلمة المرور — خرجت الأجهزة الأخرى", "toast.load_quality_failed":"تعذّر تحميل درجات الجودة: {msg}", "toast.score_range":"يجب أن تكون الدرجة رقمًا بين 0 و 100", "toast.override_set":"تم تعيين تجاوز لـ {name}", "toast.reset":"تمت إعادة تعيين {name}", "toast.aa_saved":"تم حفظ مفتاح Artificial Analysis", "toast.stored_removed":"تمت إزالة المفتاح المحفوظ", "toast.remove_key_failed":"تعذّرت إزالة المفتاح: {msg}", "toast.aa_refreshed":"تم تحديث درجات Artificial Analysis", "toast.refresh_failed":"فشل التحديث: {msg}", "toast.load_profiles_failed":"تعذّر تحميل الملفات الشخصية: {msg}", "toast.duplicated":"تم نسخ {name}", "toast.now_default":"أصبح {name} هو الافتراضي الآن", "toast.deleted":"تم حذف {name}", "toast.default_reassigned":" — الافتراضي الآن هو auto", "toast.saved_profile":"تم حفظ {name}", "toast.file_too_large":"هذا الملف كبير جدًا ليكون تصديرًا لملف شخصي.", "toast.load_integrations_failed":"تعذّر تحميل خيارات الدمج: {msg}", "toast.load_mi_failed":"تعذّر تحميل مصادر بيانات النماذج: {msg}", "toast.source_added":"أُضيف المصدر", "toast.legacy_removed":"تمت إزالة الإدخال القديم \"__custom__\"", "toast.saved_as":"تم حفظ {name} كـ {slug}. اجلب نماذجه بالأسفل.", "confirm.remove_provider":"إزالة مفتاح {name}؟ ستبدأ الطلبات الموجّهة إلى {name} بالفشل.", "confirm.remove_model":"إزالة النموذج {name}؟", "confirm.remove_custom":"إزالة المزوّد \"{name}\" ونماذجه؟", "confirm.sign_out_others":"تسجيل الخروج من كل المتصفحات الأخرى لهذا المسؤول؟", "confirm.reset_score":"إعادة تعيين {name} إلى درجة AA؟", "confirm.remove_aa_key":"إزالة مفتاح Artificial Analysis المحفوظ؟ سيعود مفتاح البيئة للعمل إن كان مضبوطًا.", "confirm.change_slug":"تغيير معرّف API من \"{old}\" إلى \"{new}\"؟\n\nكل عميل يرسل model: \"{old}\" سيتوقف عن العمل.", "confirm.delete_source":"حذف مصدر البيانات الوصفية هذا؟", "confirm.legacy_remove":"إزالة مفتاح المزوّد القديم \"__custom__\" ({prefix}) نهائيًا؟\n\nلا يُستخدم للتوجيه. احتفظ بالمفتاح في مكان آخر إن كنت لا تزال بحاجة إليه — لا يمكن استعادته.", "confirm.revoke":"إلغاء \"{name}\"؟\n\nالعملاء الذين يستخدمون هذا المفتاح سيتلقون 401 فورًا. لا يمكن التراجع — أصدر مفتاحًا جديدًا إن احتجت الوصول مجددًا.", "confirm.rotate":"تدوير \"{name}\"؟\n\nيُنشأ مفتاح بديل بنفس القيود ويُعرض مرة واحدة.\n\nموافق = إلغاء المفتاح القديم الآن (تبديل فوري).\nإلغاء = إبقاء المفتاح القديم حتى تلغيه بنفسك.", "prompt.rename_key":"إعادة تسمية المفتاح \"{name}\" إلى:", "prompt.set_score":"تعيين درجة جودة يدوية لـ {name} (0-100):", "prompt.aa_current":"درجة AA الحالية: {score}", "prompt.override_note":"ملاحظة اختيارية (لماذا التجاوز؟):", "auth.session_expired":"انتهت جلستك. سجّل الدخول مجددًا.", "auth.enter_creds":"أدخل اسم المستخدم وكلمة المرور.", "auth.creds_required":"اسم المستخدم وكلمة المرور مطلوبان.", "auth.pw_mismatch":"كلمتا المرور غير متطابقتين.", "auth.paste_token":"الصق رمز الإعداد لمرة واحدة من سجل الخادم.", "auth.signed_out":"تم تسجيل الخروج.", "auth.pw_match":"كلمتا المرور متطابقتان.", "auth.pw_mismatch_yet":"كلمتا المرور غير متطابقتين بعد.", "auth.new_pw_mismatch":"كلمتا المرور الجديدتان غير متطابقتين.", "auth.fill_three":"املأ الحقول الثلاثة كلها.", "qa.connection":"اتصال Artificial Analysis", "qa.test":"اختبار الاتصال", "qa.replace":"استبدال المفتاح", "qa.add":"إضافة مفتاح", "qa.remove":"إزالة المفتاح", "qa.last_sync":"آخر مزامنة ناجحة", "qa.last_error":"أحدث خطأ", "qa.never":"لم تتم المزامنة بعد", "qa.from_env":"من البيئة", "qa.saving":"جارٍ الحفظ…", "qa.key_hint":"يُشفّر على هذا الخادم ولا يُعرض مرة أخرى. يظل المفتاح السابق فعّالًا حتى حفظ هذا المفتاح.", "qa.daily_limit_label":"الحد اليومي للمفتاح", "qa.daily_limit_hint":"الطلبات لكل 24 ساعة، وفق صفحة حسابك في Artificial Analysis. اتركه فارغًا لاستخدام الحد الموثّق 100/يوم.", "qa.status.not_configured":"غير مُهيّأ", "qa.status.connected":"متصل", "qa.status.invalid_key":"مفتاح غير صالح", "qa.status.rate_limited":"تم بلوغ الحد", "qa.status.connection_failed":"فشل الاتصال", "qa.status.cached":"بيانات مخزّنة مؤقتًا", "pricing.legend":"التسعير", "pricing.allow_estimates":"السماح بالتقديرات المرجعية في Auto والأرخص وحدود التكلفة", "pricing.allow_estimates_help":"معطّل افتراضيًا. تُقارن أسعار المزوّد المؤكدة فقط؛ وتبقى النماذج التي لديها تقدير مرجعي فقط خارج Auto. عند التفعيل، تُوسم كل قرارات التوجيه المبنية على التقدير.", "confirm.bulk_remove_models":"إزالة {count} نموذجًا مختارًا{plural}؟ ستفشل الطلبات المثبتة إليها.", "nav.chat":"المحادثة", "tab.chat.title":"المحادثة", "tab.chat.sub":"تحدث إلى نماذجك الموزّعة. توجيه وتخزين مؤقت وقياس مثل حزم SDK.", "ui.open_chat":"افتح المحادثة", "ui.open_chat_hint":"تحدث إلى نماذجك الموزّعة من المتصفح — نفس التوجيه والتخزين المؤقت وتتبع التكلفة مثل حزم SDK.", "chat.new":"محادثة جديدة", "chat.settings_title":"إعدادات المحادثة", "chat.default_title":"محادثة جديدة", "chat.clear_history":"مسح السجل…", "chat.conversations_aria":"المحادثات", "chat.model_aria":"النموذج", "chat.regenerate":"أعد توليد الرد", "chat.empty_title":"اسأل عن أي شيء.", "chat.empty_sub":"تمر الطلبات عبر المحرّك — نفس التوجيه والتخزين المؤقت وتتبع التكلفة مثل حزم SDK.", "chat.input_placeholder":"رسالة إلى GeekCubo…", "chat.send":"إرسال", "chat.stop":"إيقاف", "chat.system_prompt":"موجّه النظام…", "chat.system_prompt_set":"موجّه النظام ✓", "chat.system_ph":"أنت مساعد مفيد…", "chat.system_help":"فارغ = استخدام افتراضي المحادثة. يُحفظ لكل محادثة.", "chat.save_prompt":"حفظ الموجّه", "chat.default_model":"النموذج الافتراضي", "chat.default_model_help":"يُستخدم للمحادثات الجديدة. منتقي المحادثة نفسه يتجاوزه.", "chat.temperature":"درجة الحرارة", "chat.max_tokens":"أقصى رموز الإخراج", "chat.default_system_prompt":"موجّه النظام الافتراضي", "chat.default_system_prompt_ph":"أنت مساعد هندسي مقتضب.", "chat.default_system_help":"ينطبق على المحادثات التي لا تملك موجّهًا خاصًا بها.", "chat.save_history":"حفظ سجل المحادثة على هذا الخادم", "chat.retention_days":"الاحتفاظ بالمحادثات لمدة (أيام)", "chat.retention_help":"تُحذف المحادثات الأقدم. فارغ = الاحتفاظ بكل شيء.", "chat.font_size":"حجم نص الرسائل", "chat.fs_small":"صغير", "chat.fs_medium":"متوسط", "chat.fs_large":"كبير", "chat.enter_to_send":"مفتاح الإدخال يرسل الرسالة", "chat.privacy_note":"تبقى المحادثات في قاعدة بيانات هذا الخادم. تُرسل الطلبات إلى المزودين الذين اخترتهم، تمامًا كما في حزم SDK.", "chat.privacy_ack":"أفهم أن حركة المحادثة تذهب إلى المزودين المُعدّين", "chat.save_settings":"حفظ الإعدادات", "chat.model_auto":"تلقائي (يختار الموجّه)", "chat.no_conversations":"لا توجد محادثات بعد.", "chat.delete_convo_title":"احذف هذه المحادثة", "chat.kbd_enter_send":"Enter للإرسال · Shift+Enter لسطر جديد", "chat.kbd_ctrl_enter_send":"Ctrl+Enter للإرسال · Enter لسطر جديد", "chat.tokens_meta":"{in} إدخال · {out} إخراج", "chat.error_note":"توقّف التوليد قبل الاكتمال.", "chat.upstream_error":"أعاد النموذج الأعلى خطأً.", "toast.chat_load_failed":"تعذّر تحميل بيانات المحادثة: {msg}", "toast.chat_failed":"فشل طلب المحادثة: {msg}", "toast.chat_convo_deleted":"تم حذف المحادثة", "toast.chat_cleared":"تم مسح {count} محادثة", "toast.chat_temp_range":"يجب أن تكون درجة الحرارة بين 0 و 2", "toast.chat_settings_saved":"تم حفظ إعدادات المحادثة", "toast.chat_open_convo":"افتح محادثة أولاً", "toast.chat_saved_prompt":"تم حفظ موجّه النظام لهذه المحادثة", "confirm.delete_conversation":"حذف هذه المحادثة؟\n\nتُزال الرسائل من قاعدة بيانات الخادم. تبقى سجلات الاستخدام والتكلفة في التحليلات.", "confirm.clear_chat_history":"حذف جميع المحادثات المحفوظة؟\n\nتُزال كل رسائل المحادثة المخزنة على هذا الخادم. تبقى سجلات الاستخدام والتكلفة في التحليلات.", "q.ov_score":"درجة يدوية (0–100)", "q.ov_note":"ملاحظة", "q.ov_model_ph":"مثال: openai/gpt-4o, anthropic/claude-…", "q.ov_note_ph":"لماذا يتجاوز هذا درجة AA", "q.ov_apply":"تطبيق التجاوز", "q.ov_clear":"إزالة التجاوز", "q.ov_help":"معرّف نموذج واحد أو أكثر، مفصولة بفواصل — يُطبَّق التجاوز على كل نموذج مُدرج. الدرجات اليدوية تتفوق دائمًا على درجات AA.", "toast.q_ids_required":"أدخل معرّف نموذج واحد على الأقل", "toast.q_too_many":"العملية الجماعية محدودة بـ 500 معرّف نموذج", "toast.q_bulk_set":"تم تعيين التجاوز لـ {count} نموذج/نماذج", "toast.q_bulk_clear":"تمت إزالة التجاوزات من {count} نموذج/نماذج", "providers.bulk_actions":"إجراءات جماعية للنماذج", "providers.select_all":"تحديد الكل", "providers.selected_count":"تم تحديد {count}", "providers.bulk_capability":"القدرة", "providers.bulk_capability_state":"حالة القدرة", "providers.cap_tools":"الأدوات", "providers.cap_vision":"الرؤية", "providers.cap_supported":"مدعوم", "providers.cap_unsupported":"غير مدعوم", "providers.cap_unknown":"غير معروف", "providers.cap_catalog":"استخدام الفهرس", "providers.cap_json_mode":"وضع JSON", "providers.cap_json_schema":"مخطط JSON", "providers.apply":"تطبيق", "providers.enable":"تمكين", "providers.disable":"تعطيل", "providers.remove_selected":"إزالة المحدد", "providers.resolve_metadata":"مطابقة", "toast.metadata_resolved":"البيانات الوصفية: {resolved} مطابق، {ambiguous} ملتبس، {unmatched} بلا تطابق، {failed} فاشل.", "select.search_ph":"ابحث في مفاتيح الكتالوج…", "providers.catalog_key_ph":"ابحث في مفاتيح الكتالوج…", "select.remove_item":"إزالة {name}", "select.use_custom":"استخدام \"{name}\"", "select.no_matches":"لا توجد نماذج مطابقة", "select.more_results":"{count} أخرى — تابع الكتابة للتضييق", "q.ov_model_search_ph":"ابحث عن النماذج واخترها…", "q.ov_help_picker":"ابحث عن نموذج أو أكثر واختره، أو حدّد صفوفًا في الجدول أدناه. الدرجات اليدوية تتقدم دائمًا على درجات AA.", "q.filter_ph":"تصفية النماذج…", "q.select_filtered":"تحديد النتائج المصفّاة", "q.select_all_filtered":"تحديد كل النماذج المصفّاة", "q.deselect_all":"إلغاء تحديد الكل", "q.bulk_set":"تعيين درجة للمحدد", "q.bulk_clear":"مسح التجاوزات المحددة", "q.select_model":"تحديد {name}", "confirm.q_bulk_clear":"مسح التجاوزات اليدوية لـ {count} من النماذج المحددة؟", "qa.daily_limit_short":"الحد اليومي", "chat.attach":"إرفاق ملفات", "chat.attach_drop":"أفلت الملفات للإرفاق", "chat.attach_remove":"إزالة المرفق", "chat.attach_unreadable":"تعذّرت قراءة هذا الملف؛ يُرسَل اسمه فقط.", "chat.attach_uploading":"جارٍ الرفع…", "chat.attach_too_large":"كبير جدًا (الحد الأقصى {max} ميغابايت)", "toast.chat_attach_failed":"تعذّر إرفاق {name}: {msg}", "toast.chat_attach_disabled":"المرفقات معطّلة على هذا الخادم.", "toast.chat_attach_too_many":"{max} مرفقات كحد أقصى لكل رسالة.", "toast.chat_attach_extract_failed":"{name}: تعذّرت القراءة ({msg})", "toast.chat_attach_wait":"انتظر انتهاء عمليات الرفع.", "chat.search_toggle":"البحث في الويب", "chat.search_settings":"البحث في الويب", "chat.search_help":"عند التفعيل، يبحث GeekCubo في الويب قبل الإجابة ويستشهد بالصفحات المستخدمة. تُحقن النتائج كرسالة نظام، لذا يمكن لأي نموذج استخدامها.", "chat.search_mode":"وضع البحث", "chat.search_mode_off":"متوقف", "chat.search_mode_manual":"يدوي (لكل رسالة)", "chat.search_mode_auto":"تلقائي (محجوز)", "chat.search_mode_help":"يعرض الوضع اليدوي مفتاحًا في مربع الإدخال. الوضع التلقائي محجوز وغير مُنفَّذ بعد.", "chat.search_backend":"خدمة البحث", "chat.search_backend_none":"اختر خدمة…", "chat.search_backend_searxng":"SearXNG (استضافة ذاتية)", "chat.search_backend_brave":"واجهة Brave Search", "chat.search_backend_tavily":"Tavily", "chat.search_url":"رابط SearXNG", "chat.search_url_ph":"http://searxng:8080/", "chat.search_url_help":"الرابط الأساسي لنسخة SearXNG لديك. يوفّره ملف search في المثبّت على الشبكة الداخلية.", "chat.search_api_key":"مفتاح API", "chat.search_api_key_ph":"ألصق مفتاحًا جديدًا لاستبدال المفتاح المحفوظ", "chat.search_key_clear":"إزالة المفتاح المحفوظ", "chat.search_key_help":"يُحفظ مشفّرًا على هذا الخادم ولا يُعرض مجددًا. تتطلب Brave وTavily مفتاحًا، بينما لا يتطلب SearXNG ذلك.", "chat.search_max_searches":"أقصى عدد بحث لكل محادثة", "chat.search_max_results":"النتائج لكل بحث", "chat.search_max_fetches":"الصفحات المجلوبة لكل بحث", "chat.search_timeout":"مهلة البحث (ثوانٍ)", "chat.search_test":"اختبار الاتصال", "chat.search_testing":"جارٍ الاختبار…", "chat.search_test_ok":"{count} نتيجة خلال {ms} مللي ثانية", "chat.search_test_failed":"فشل اختبار البحث: {msg}", "chat.search_key_state_unset":"لا يوجد مفتاح محفوظ", "chat.search_key_state_set":"المفتاح محفوظ", "chat.search_key_state_undecryptable":"تعذّر فك تشفير المفتاح المحفوظ", "chat.context_budget":"السياق: {tokens} / {budget} رمزًا", "chat.context_omitted":"تم حذف {count} رسالة سابقة", "chat.sources":"المصادر", "chat.search_used":"البحث في الويب: {backend}", "toast.search_saved":"تم حفظ إعدادات البحث في الويب", "toast.search_save_failed":"تعذّر حفظ إعدادات البحث: {msg}", "toast.search_test_failed":"فشل اختبار البحث في الويب", "nav.local":"الذكاء الاصطناعي المحلي", "tab.local.title":"الذكاء الاصطناعي المحلي", "tab.local.sub":"قدّم النماذج من أجهزتك الخاصة عبر هذا الموجّه.", "local.title":"اتصال الذكاء الاصطناعي المحلي", "local.sub":"وجّه الطلبات إلى نماذج تعمل على أجهزتك الخاصة. يتصل موصّل صغير بهذا الخادم من الداخل إلى الخارج، لذا لا تُفتح أي منافذ ولا حاجة إلى نفق وارد.", "local.refresh":"تحديث", "local.setup_button":"إعداد جهاز", "local.feature_off_title":"اتصال الذكاء الاصطناعي المحلي معطّل على الخادم", "local.feature_off_body":"اضبط LOCAL_CONNECT_ENABLED=true في بيئة الخادم وأعد التشغيل، ثم أعد تحميل هذه الصفحة.", "local.url_missing_title":"لم يتم تكوين عنوان عام", "local.url_missing_body":"اضبط LOCAL_CONNECT_PUBLIC_URL على العنوان الذي يجب أن يتصل به الموصّلات (مثل https://example.com) حتى يتم ملء أمر التثبيت وملفات الخدمة.", "local.settings_title":"سلوك التوجيه", "local.settings_sub":"يتحكم في مشاركة النماذج المحلية في التوجيه التلقائي وفي إمكانية رجوع الطلب إلى السحابة.", "local.set_enabled":"السماح بالأجهزة المحلية للتوجيه", "local.set_auto":"تضمين النماذج المحلية في الاختيار التلقائي", "local.set_no_fallback":"عدم الرجوع إلى السحابة أبدًا عند فشل نموذج محلي", "local.settings_help":"لا تُؤخذ النماذج المحلية في الاعتبار للتوجيه التلقائي إلا عندما يكون سعرها صفرًا مؤكدًا ويكون الجهاز معتمدًا ومتصلًا. عند تفعيل \"عدم الرجوع أبدًا\"، يفشل الطلب المحلي فقط بدلًا من أن يخدمه مزوّد سحابي.", "local.save_settings":"حفظ", "local.settings_saved":"تم حفظ إعدادات التوجيه المحلي.", "local.machines_title":"الأجهزة", "local.machines_sub":"كل جهاز هو موصّل واحد. تظهر الأجهزة المعلّقة لكن لا يُوجَّه إليها أي حركة حتى تعتمدها.", "local.machines_empty":"لا توجد أجهزة بعد. استخدم \"إعداد جهاز\" لإنشاء رمز تسجيل.", "local.enrollments_title":"رموز التسجيل", "local.enrollments_sub":"رموز تُستخدم مرة واحدة تتيح للموصّل بالتسجيل. يُستهلك كل رمز عند أول اتصال لجهاز.", "local.new_code":"رمز جديد", "local.install_title":"تثبيت الموصّل", "local.install_sub":"شغّل هذا على الجهاز الذي يستضيف نماذجك (Ollama أو LM Studio أو vLLM أو llama.cpp أو أي خادم متوافق مع [OI]).", "local.service_files":"تشغيله كخدمة", "local.delete":"حذف", "local.never":"أبدًا", "local.ctx_suffix":"سياق", "local.ctx_unknown":"السياق غير معروف", "local.no_models":"لم يُبلّغ هذا الجهاز عن أي نماذج بعد.", "local.no_enrollments":"لا توجد رموز تسجيل.", "local.enroll_active":"نشط", "local.enroll_used":"مستخدم", "local.status_online":"متصل", "local.status_offline":"غير متصل", "local.status_pending":"بانتظار الاعتماد", "local.status_approved":"معتمد", "local.status_revoked":"ملغى", "local.pending_note":"هذا الجهاز بانتظار الاعتماد. النماذج مدرجة لكن لن تُوجَّه إليها حركة.", "local.action_approve":"اعتماد", "local.action_discover":"اكتشاف النماذج", "local.action_revoke":"إلغاء", "local.action_rotate":"تدوير بيانات الاعتماد", "local.action_delete":"حذف", "local.meta_host":"اسم المضيف", "local.meta_platform":"المنصة", "local.meta_agent":"إصدار الموصّل", "local.meta_adapters":"المحوّلات", "local.meta_seen":"آخر ظهور", "local.col_model":"النموذج", "local.col_adapter":"نوع المحوّل", "local.col_context":"السياق", "local.col_caps":"الإمكانات", "local.col_enabled":"مُمكَّن", "local.kpi_machines":"الأجهزة", "local.kpi_online":"متصل الآن", "local.kpi_pending":"بانتظار الاعتماد", "local.kpi_models":"النماذج", "local.toast_approved":"تم اعتماد الجهاز.", "local.toast_revoked":"تم إلغاء الجهاز.", "local.toast_deleted":"تم حذف الجهاز.", "local.toast_discovered":"تم تحديث قائمة النماذج.", "local.confirm_revoke":"إلغاء هذا الجهاز؟ سيُقطع اتصال موصّله فورًا ولن يتمكن من إعادة الاتصال حتى تدوّر بيانات اعتماده.", "local.confirm_delete_machine":"حذف هذا الجهاز وقائمة نماذجه؟ لا يمكن التراجع عن ذلك.", "local.confirm_rotate":"تدوير بيانات اعتماد هذا الجهاز؟ يستمر الموصّل قيد التشغيل حتى يعيد الاتصال، ثم تُرفض بيانات الاعتماد القديمة.", "local.confirm_delete_enrollment":"حذف رمز التسجيل هذا؟", "local.credential_once_title":"انسخ بيانات الاعتماد الجديدة الآن", "local.credential_once_body":"تُعرض مرة واحدة فقط. خزّنها في إعدادات الموصّل على الجهاز.", "local.wizard_title":"ربط جهاز محلي", "local.wizard_close":"إغلاق", "local.wizard_back":"رجوع", "local.wizard_next":"التالي", "local.wizard_done":"تم", "local.step1":"التمكين", "local.step2":"رمز التسجيل", "local.step3":"التثبيت", "local.step4":"التسجيل", "local.step5":"التشغيل", "local.step6":"الموافقة", "local.step7":"النماذج", "local.step8":"التوجيه التلقائي", "local.w0_title":"شغّل الميزة", "local.w0_body":"اتصال الذكاء الاصطناعي المحلي ميزة على جانب الخادم. يجب تمكينها قبل أن تتمكن الموصّلات من التسجيل.", "local.w0_ready":"الميزة مُمكّنة. تابع لإنشاء رمز تسجيل.", "local.w0_blocked":"الميزة معطّلة على هذا الخادم. اضبط LOCAL_CONNECT_ENABLED=true وأعد التشغيل، ثم أعد تحميل هذه الصفحة.", "local.w1_title":"أنشئ رمز تسجيل", "local.w1_body":"رمز يُستخدم مرة واحدة يصرّح لموصّل واحد بالتسجيل. تنتهي صلاحيته بعد فترة قصيرة.", "local.w1_name":"اسم الجهاز (اختياري)", "local.w1_name_ph":"مثال: مكتب-gpu", "local.w1_name_help":"تسمية للتعرف على هذا الجهاز في القائمة. يمكنك إعادة تسميته لاحقًا.", "local.w1_created":"تم إنشاء رمز التسجيل", "local.w2_title":"ثبّت حزمة الموصّل", "local.w2_body":"على الجهاز الذي يستضيف نماذجك، ثبّت الموصّل. يلزم Python 3.11 أو أحدث.", "local.w2_note":"ثبّته في بيئة افتراضية لتبقيه معزولًا عن حزم النظام.", "local.w3_title":"سجّل الجهاز", "local.w3_body":"شغّل أمر التسجيل مع الرمز من الخطوة 2. تُكتب بيانات الاعتماد في ملف إعدادات الموصّل.", "local.w3_note":"الرمز يُستخدم مرة واحدة. إذا انتهت صلاحيته فأنشئ رمزًا جديدًا.", "local.w4_title":"شغّل الموصّل", "local.w4_body":"شغّل الموصّل في المقدمة لتراقب اتصاله، ثم انقله إلى خدمة.", "local.w4_note":"يبقي الموصّل اتصال WebSocket صادرًا واحدًا مفتوحًا ويعيد الاتصال تلقائيًا.", "local.w5_title":"انتظر ظهور الجهاز", "local.w5_body":"بمجرد اتصال الموصّل سيظهر الجهاز هنا. حدّث الصفحة إذا استغرق لحظة.", "local.w5_seen":"تم اتصال {name}.", "local.w5_waiting":"لم يتصل أي جهاز بعد.", "local.w5_recheck":"تحقق مرة أخرى", "local.w6_title":"اعتمد الجهاز", "local.w6_body":"يبقى الجهاز الجديد معلّقًا حتى يعتمده مسؤول. لا يُوجَّه إليه أي شيء قبل ذلك.", "local.w6_none":"لا يوجد جهاز لاعتماده بعد.", "local.w6_must_approve":"اعتمد الجهاز المعلّق قبل المتابعة.", "local.w7_title":"مكّن النماذج المحلية في التوجيه التلقائي", "local.w7_body":"فعّل \"تضمين النماذج المحلية في الاختيار التلقائي\" ومكّن النماذج التي تريد التوجيه إليها. لا تُختار النماذج المحلية للتوجيه التلقائي إلا عندما يكون سعرها صفرًا مؤكدًا.", "local.w7_done":"اكتمل الإعداد. تظهر النماذج المحلية الآن في صفحتي المزوّدين والتوجيه." },
  ko: { "q.tabs_label":"품질 섹션", "q.tab_models":"모델", "q.tab_scores":"품질 점수", "q.tab_aa":"Artificial Analysis 연결", "q.col_availability":"사용 가능 여부", "q.avail_yes":"사용 가능", "q.avail_no":"공급자 키 없음", "q.avail_no_title":"이 모델을 제공하는 설정된 공급자 키가 없습니다. 벤치마크 데이터만으로는 모델을 배포할 수 없습니다.", "q.sync_title":"벤치마크 동기화", "q.sync_last_ok":"마지막 성공한 동기화", "q.sync_last_attempt":"최근 시도", "q.sync_returned":"AA가 반환한 모델 수", "q.sync_matched":"카탈로그와 일치", "q.sync_unmatched":"일치하지 않음", "q.sync_overrides":"수동 점수", "q.sync_outcome_ok":"성공", "q.sync_outcome_failed":"실패", "q.sync_need_key":"벤치마크 점수를 동기화하려면 Artificial Analysis 탭에서 키를 추가하세요. 수동 점수는 키 없이도 작동합니다.", "q.sync_never":"이 키로는 아직 동기화하지 않았습니다. AA에서 새로 고침을 사용하세요.", "q.sync_no_models":"마지막 동기화에서 모델이 반환되지 않았습니다.", "q.status_line":"벤치마크 데이터가 있는 모델 {matched}개 · 수동 점수 {overrides}개", "q.src.live":"최신", "q.src.stale_cache":"캐시됨 (AA에 연결할 수 없음)", "q.src.stale_db":"캐시됨 (저장된 스냅샷)", "q.src.error":"동기화 실패", "q.src.missing_key":"API 키 없음", "q.auto_status":"자동 라우팅 상태", "q.auto_status_hint":"지금 model=\"auto\"가 선택할 모델입니다. 벤치마크 동기화가 아니라 설정된 공급자에 따라 달라집니다.", "q.auto_no_provider":"현재 요구 사항을 충족하는 배포 가능한 모델이 없습니다. 공급자 페이지에서 키를 추가하세요. 이는 Artificial Analysis 동기화와 별개입니다.", "qa.credential":"API 키", "qa.cred_stored":"이 서버에 저장됨(암호화)", "qa.cred_env":"서버 환경 변수에서", "qa.last_test":"마지막 연결 테스트", "qa.last_test_ok":"마지막 성공한 테스트", "qa.not_tested":"아직 테스트하지 않음", "qa.sync_status":"벤치마크 동기화", "qa.tier":"{tier} 요금제", "qa.troubleshooting":"연결 문제 해결", "qa.status.key_configured":"키 설정됨", "qa.sync.not_configured":"설정 안 됨", "qa.sync.never_synced":"동기화한 적 없음", "qa.sync.synced":"동기화됨", "qa.sync.sync_failed":"동기화 실패", "qa.err.invalid_key":"잘못된 키", "qa.err.insufficient_tier":"요금제에 엔드포인트가 포함되지 않음", "qa.err.endpoint_retired":"엔드포인트 종료됨", "qa.err.rate_limited":"요청 한도 도달", "qa.err.timeout":"시간 초과", "qa.err.malformed_response":"예상치 못한 응답", "qa.err.no_data":"반환된 모델 없음", "qa.err.no_catalog_match":"카탈로그 일치 없음", "qa.err.server_error":"AA 서버 오류", "qa.err.connection_failed":"연결 실패", "auth.tagline":"하나의 게이트웨이, 모든 AI 모델.", "auth.welcome":"다시 오신 것을 환영합니다", "auth.subtitle":"이 GeekCubo 설치의 관리자 콘솔에 로그인하세요.", "auth.api_key":"API 키", "auth.continue":"계속", "nav.search":"검색", "nav.overview":"개요", "nav.providers":"공급자", "nav.routing":"경로 지정", "nav.analytics":"분석", "nav.api_keys":"API 키", "nav.help_docs":"도움말 및 문서", "nav.sign_out":"로그아웃", "status.connected":"연결됨", "status.disconnected":"연결 끊김", "auth.checking":"확인 중…", "auth.welcome_aboard":"환영합니다.", "auth.key_invalid":"키가 올바르지 않습니다. sk-geek- 접두사를 확인하세요…", "tab.overview.title":"개요", "tab.overview.sub":"싱글 테넌트 LLM 라우터를 한눈에 확인하세요.", "tab.providers.title":"공급자 키", "tab.providers.sub":"BYOK — 저장 시 암호화되며 상위 LLM 호출에 사용됩니다.", "tab.routing.title":"라우팅", "tab.routing.sub":"model='auto'가 요청별로 적절한 모델을 고르는 방식입니다.", "tab.analytics.title":"분석", "tab.analytics.sub":"로컬 전용 비용, 지연 시간, 요청 기록.", "tab.keys.title":"API 키", "tab.keys.sub":"SDK 및 CLI 추론 트래픽을 인증하는 sk-geek-* 키.", "nav.quality":"품질", "tab.quality.title":"품질 점수", "tab.quality.sub":"품질 라우팅 전략에 사용하는 실제 벤치마크 점수입니다. Artificial Analysis에서 가져옵니다.", "auth.username":"사용자 이름", "auth.password":"비밀번호", "auth.sign_in":"로그인", "nav.security":"보안", "tab.security.title":"보안", "tab.security.sub":"관리자 계정, 비밀번호, 세션.", "tab.profiles.title":"라우팅 프로필", "tab.profiles.sub":"클라이언트가 모델 ID로 선택하는 이름이 지정된 Auto 구성입니다.", "tab.integrations.title":"도구 연결", "tab.integrations.sub":"OpenCode, Claude Code, Cursor 등을 위한 바로 사용 가능한 구성입니다.", "tab.intelligence.title":"모델 데이터", "tab.intelligence.sub":"모델 가격과 한도의 출처입니다.", "auth.loading":"불러오는 중…", "auth.checking_status":"관리자 상태를 확인하는 중입니다.", "auth.signin_title":"로그인", "auth.signin_sub":"이 GeekCubo 설치에 대한 관리자 액세스입니다.", "auth.forgot":"비밀번호를 잊으셨나요?", "auth.reset_hint":"호스트 또는 컨테이너에서 재설정하세요:", "auth.reset_note":"키, 공급자, 사용량은 영향을 받지 않습니다.", "auth.setup_title":"관리자 계정 만들기", "auth.setup_sub":"이 GeekCubo 설치를 관리합니다: 공급자 자격 증명, API 키, 라우팅.", "auth.min_password":"8자 이상", "auth.confirm_password":"비밀번호 확인", "auth.setup_token":"설정 토큰", "auth.from_log":"서버 로그에서", "auth.create_admin":"관리자 만들기", "auth.where_token":"설정 토큰은 어디에 있나요?", "auth.token_hint":"처음 시작할 때 서버 로그에 출력됩니다. 새로 발급하려면:", "auth.toggle_password":"비밀번호 표시 또는 숨기기", "ov.spend":"지출 (7일)", "ov.savings":"라우팅 절감액", "ov.p50":"p50 지연시간", "ov.models":"배포 가능 모델", "ov.quickstart":"빠른 시작", "ov.recent":"최근 활동", "prov.title":"공급자 키", "prov.tab_std":"표준 공급자", "prov.tab_custom":"사용자 공급자", "routing.strategy":"라우팅 전략", "routing.pools":"모델 풀", "routing.advanced":"폴백, 에스컬레이션 및 연속성", "routing.explain":"라우팅 결정 테스트", "profiles.title":"라우팅 프로필", "int.title":"AI 도구 연결", "md.title":"모델 데이터 소스", "md.lookup":"가격 조회", "an.spend":"모델별 지출", "an.latency":"공급자별 지연시간", "an.recent":"최근 요청", "keys.title":"라우터 API 키", "sec.sessions":"세션", "q.setup":"품질 점수 설정", "q.models":"모델", "preset.heading":"프리셋으로 시작", "preset.sub":"템플릿은 편집기에 미리 채워진 채로 열립니다. 저장 전에 자유롭게 조정하세요.", "preset.economy":"요청마다 가장 저렴한 유능한 모델을 선택합니다. 최소 비용, 품질 하한 없음.", "preset.premium":"가격과 무관하게 가장 강력한 모델을 우선합니다. 품질이 중요한 작업용.", "preset.coding":"도구 호출과 긴 프롬프트는 Hard 풀로 보냅니다. 에이전트·편집기 작업용.", "preset.fast":"풀 내에서 낮은 지연을 선호하는 균형 라우팅.", "ui.profiles":"프로필", "ui.security":"보안", "ui.api_keys":"API 키", "ui.connect_a_tool":"도구 연결", "ui.model_data":"모델 데이터", "ui.connecting":"연결 중…", "ui.language":"언어", "ui.light":"라이트", "ui.system":"시스템", "ui.dark":"다크", "ui.openai_compatible_base_url":"OpenAI 호환 기본 URL", "ui.copy":"복사", "ui.use_this_in_any_openai_compatible_client":"모든 OpenAI 호환 클라이언트에서 사용할 수 있습니다.", "ui.signed_in":"로그인됨", "ui.security_and_sessions":"보안 및 세션", "ui.api_keys_2":"API 키", "ui.sign_out":"로그아웃", "ui.you_re_up_point_any_openai_sdk_at_your_b":"준비 완료 — 아무 OpenAI SDK나 기본 URL로 지정하세요.", "ui.last_5_requests_routed_through_this_serv":"이 서버를 거친 최근 5개 요청.", "ui.view_all":"모두 보기", "ui.no_requests_yet":"아직 요청이 없습니다.", "ui.new_here_get_fully_set_up_in_2_minutes":"처음이신가요? 2분이면 모두 설정됩니다", "ui.re_enter_as_a_named_provider":"이름이 있는 공급자로 다시 입력", "ui.remove_legacy_entry":"레거시 항목 제거", "ui.provider":"공급자", "ui.others_openai_format":"기타 (OpenAI 형식)", "ui.api_key":"API 키", "ui.provider_name":"공급자 이름", "ui.display_name_a_unique_internal_slug_is_d":"표시 이름입니다. 고유한 내부 슬러그가 자동으로 생성됩니다.", "ui.api_base_url":"API 기본 URL", "ui.usually_ends_in_v1_must_be_https_unless_":"보통 /v1로 끝납니다. 호스트가 CUSTOM_PROVIDER_ALLOWED_LOCAL_HOSTS에 없으면 https여야 합니다.", "ui.api_key_2":"API 키", "ui.encrypted_at_rest_never_displayed_again_":"저장 시 암호화되며 이후 다시 표시되지 않습니다.", "ui.prefix":"접두사", "ui.status":"상태", "ui.no_provider_keys_yet":"아직 공급자 키가 없습니다", "ui.add_at_least_one_to_start_routing_real_t":"실제 트래픽을 라우팅하려면 최소 하나를 추가하세요. 위에서 공급자를 고르거나 빠른 추가를 클릭하세요.", "ui.lowest_cost_that_clears_your_quality_flo":"품질 하한을 넘는 가장 저렴한 선택. 공급자 수와 무관하게 안전한 기본값입니다.", "ui.recommended":"권장", "ui.lowest_per_token_cost_meeting_the_reques":"요청의 요구 사항을 충족하면서 토큰당 비용이 가장 낮음. 출력 품질은 달라질 수 있습니다.", "ui.highest_score_from_artificial_analysis_o":"Artificial Analysis 점수 또는 수동 재정의 중 가장 높은 값. 점수가 없으면 가격을 근사치로 사용합니다.", "ui.re_ranks_by_observed_success_rate_and_la":"각 모델의 요청이 여기에서 20건을 넘으면 실측 성공률과 지연으로 다시 순위를 매깁니다. 그 전까지는 균형.", "ui.sends_each_request_to_your_mundane_or_ha":"관측 가능한 신호(도구, 규모, 길이)에 따라 각 요청을 Mundane 또는 Hard 풀로 보냅니다.", "ui.highest_throughput_and_lowest_first_toke":"벤치마크 데이터에서 처리량이 가장 높고 첫 토큰 지연이 가장 낮음. 기존 설정 호환을 위해 유지합니다.", "ui.legacy":"레거시", "ui.registered_models":"등록된 모델", "ui.show":"표시", "ui.deployable":"배포 가능", "ui.custom_providers":"사용자 공급자", "ui.model":"모델", "ui.capabilities":"기능", "ui.context":"컨텍스트", "ui.price_1m_in_out":"가격 /1M (입력 · 출력)", "ui.availability":"가용성", "ui.pools":"풀", "ui.previous":"이전", "ui.next":"다음", "ui.fallback_and_escalation_always_keep_the_":"폴백과 에스컬레이션은 항상 요청에 필요한 기능을 유지합니다. 결정은 요청 시작 전에 이루어지며, 스트림 도중에 모델이 바뀌지 않습니다.", "ui.maximum_attempts_primary_fallbacks":"최대 시도 횟수(기본 + 폴백)", "ui.what_counts_as_retryable":"재시도 대상", "ui.quality_floor_percentile_0_off":"품질 하한(백분위, 0 = 해제)", "ui.needs_quality_scores_ignored_and_reporte":"품질 점수가 필요합니다. 없으면 무시되며 그 사실이 표시됩니다.", "ui.what_the_quality_floor_does":"품질 하한의 역할", "ui.balanced_weighs_price_against_quality_th":"균형은 가격과 품질을 함께 고려합니다. 하한은 해당 백분위 아래 모델을 제외하므로 매우 저렴하지만 약한 모델이 선택되지 않습니다. 0으로 두면 하한이 사라집니다.", "ui.messages":"메시지 수 ≥", "ui.prompt_characters":"프롬프트 문자 수 ≥", "ui.how_request_signals_are_measured":"요청 신호 측정 방식", "ui.mode":"모드", "ui.off":"해제", "ui.manual_client_sends_x_geek_escalate":"수동(클라이언트가 x-geek-escalate 전송)", "ui.auto_after_repeated_upstream_failures":"자동(업스트림 실패가 반복된 후)", "ui.failures_before_escalating":"에스컬레이션 전 실패 횟수", "ui.max_escalations_per_conversation":"대화당 최대 에스컬레이션 수", "ui.destination_pool":"대상 풀", "ui.when_escalation_triggers":"에스컬레이션 발동 조건", "ui.remember_for_minutes":"기억 기간(분)", "ui.what_continuity_does":"연속성의 역할", "ui.save_routing_policy":"라우팅 정책 저장", "ui.dry_run_shows_which_model_auto_would_cho":"드라이런: Auto가 어떤 모델을 왜 선택하는지 보여줍니다. 업스트림으로 아무것도 전송되지 않습니다.", "ui.messages_2":"메시지 수", "ui.prompt_chars":"프롬프트 문자 수", "ui.explain":"설명", "ui.three_filters_applied_in_order":"세 개의 필터를 순서대로 적용합니다.", "ui.how_each_strategy_maps_to_litellm_router":"각 전략이 LiteLLM Router에 매핑되는 방식", "ui.strategy":"전략", "ui.import_json":"JSON 가져오기", "ui.new_profile":"새 프로필", "ui.generates_configuration_that_points_a_cl":"이 GeekCubo를 가리키는 클라이언트 구성을 생성합니다. 키는 환경 변수로 참조되며 파일에 포함되지 않습니다.", "ui.search_tools":"도구 검색", "ui.routing_profile_or_model":"라우팅 프로필 또는 모델", "ui.endpoint":"엔드포인트", "ui.format":"형식", "ui.download":"다운로드", "ui.add_source":"소스 추가", "ui.name":"이름", "ui.https_url_models_dev_compatible_json":"HTTPS URL(models.dev 호환 JSON)", "ui.save_source":"소스 저장", "ui.cancel":"취소", "ui.shows_what_each_enabled_source_reports_f":"활성화된 각 소스가 해당 모델에 대해 보고하는 값과 GeekCubo가 사용할 값을 보여줍니다. 직접 설정한 가격이 항상 우선합니다.", "ui.look_up":"조회", "ui.routing":"라우팅", "ui.volume":"볼륨", "ui.routing_decisions":"라우팅 결정", "ui.how_auto_requests_were_classified_and_wh":"Auto 요청이 어떻게 분류되고 어디로 갔는지.", "ui.by_tier":"계층별", "ui.by_strategy":"전략별", "ui.by_routing_id":"라우팅 ID별", "ui.top_models_served":"가장 많이 처리된 모델", "ui.reliability":"신뢰성", "ui.errors_by_cause":"원인별 오류", "ui.compare_against_a_baseline_model":"기준 모델과 비교", "ui.none":"없음", "ui.compare":"비교", "ui.how_the_comparison_is_calculated":"비교 계산 방식", "ui.p50_and_p99_sourced_from_local_request_l":"p50 및 p99 — 로컬 요청 로그에서 산출.", "ui.requests":"요청", "ui.newest_first_click_a_row_to_copy_its_tra":"최신순. 행을 클릭하면 trace ID가 복사됩니다.", "ui.when":"시각", "ui.tokens_in_out":"토큰(입력 / 출력)", "ui.latency":"지연", "ui.no_traffic_yet":"아직 트래픽이 없습니다", "ui.once_you_start_sending_requests_they_ll_":"요청을 보내기 시작하면 여기에 실시간으로 표시됩니다.", "ui.expires":"만료", "ui.never":"만료 없음", "ui.7_days":"7일", "ui.30_days":"30일", "ui.90_days":"90일", "ui.1_year":"1년", "ui.use_it_with_opencode":"OpenCode에서 사용:", "ui.created":"생성", "ui.last_used":"마지막 사용", "ui.actions":"작업", "ui.no_api_keys":"API 키 없음", "ui.generate_one_above_to_start_sending_requ":"위에서 하나를 생성하면 SDK나 CLI에서 요청을 보낼 수 있습니다.", "ui.administrator":"관리자", "ui.the_single_local_account_that_controls_t":"이 설치를 제어하는 유일한 로컬 계정입니다.", "ui.password_was_reset_from_the_command_line":"명령줄에서 비밀번호가 재설정되었습니다", "ui.change_password":"비밀번호 변경", "ui.current_password":"현재 비밀번호", "ui.new_password":"새 비밀번호", "ui.confirm_new_password":"새 비밀번호 확인", "ui.update_password":"비밀번호 업데이트", "ui.signed_in_browsers_for_this_administrato":"이 관리자로 로그인된 브라우저입니다. 세션은 12시간 또는 60분 유휴 후 만료됩니다.", "ui.log_out_all_other_sessions":"다른 모든 세션 로그아웃", "ui.device":"기기", "ui.last_active":"마지막 활동", "ui.local_recovery":"로컬 복구", "ui.password_recovery_is_local_only_by_desig":"비밀번호 복구는 설계상 로컬 전용입니다 — 이메일 재설정이 없고 비밀번호를 변경할 수 있는 공개 엔드포인트도 없습니다.", "ui.open_a_shell_where_geekcubo_runs_host_or":"GeekCubo가 실행되는 호스트나 컨테이너에서 셸을 엽니다.", "ui.choose_a_new_password_at_the_prompt_all_":"프롬프트에서 새 비밀번호를 입력합니다. 모든 대시보드 세션이 로그아웃되며, API 키·공급자·사용 데이터는 그대로 유지됩니다.", "ui.artificial_analysis_api_key":"Artificial Analysis API 키", "ui.optional":"(선택)", "ui.save_key":"키 저장", "ui.remove_stored_key":"저장된 키 제거", "ui.how_quality_scoring_works":"품질 점수 산정 방식", "ui.paste_it_above_and_save_it_is_encrypted_":"위에 붙여넣고 저장하세요. 암호화되어 저장되며, 캐시된 내용은 폐기되어 다음 새로고침에서 새 키를 사용합니다.", "ui.quality_scores":"품질 점수", "ui.where_these_numbers_come_from":"이 수치의 출처", "ui.manual":"수동", "ui.effective":"적용값", "ui.m_blended":"$/M 통합", "ui.help_and_docs":"도움말 및 문서", "ui.what_is_geekcubo":"GeekCubo란?", "ui.60_second_quickstart":"60초 빠른 시작", "ui.keyboard_shortcuts":"키보드 단축키", "ui.switch_tabs":"탭 전환", "ui.command_palette":"명령 팔레트", "ui.toggle_this_help":"이 도움말 표시 전환", "ui.close_drawers_palette":"드로어 / 팔레트 닫기", "ui.going_further":"더 알아보기", "js.ov_empty_a":"아직 요청이 없습니다.", "js.ov_empty_b":"첫 호출을 보내면 여기에 표시됩니다.", "js.ra_unavailable":"라우팅 분석을 사용할 수 없습니다.", "js.no_spend":"이 기간에 기록된 지출이 없습니다.", "js.no_traffic":"아직 트래픽이 없습니다", "toast.copied":"클립보드에 복사됨", "toast.copy_blocked":"복사할 수 없음 — 브라우저가 차단했습니다", "toast.signed_in":"{name}로 로그인됨", "toast.admin_created":"관리자 {name} 생성됨", "toast.signed_out":"로그아웃됨", "toast.load_providers_failed":"공급자를 불러올 수 없음: {msg}", "toast.removed_provider":"{name} 제거됨", "toast.api_key_empty":"API 키는 비워둘 수 없습니다", "toast.saved_provider":"{name} 키 저장됨", "toast.load_custom_failed":"사용자 공급자를 불러올 수 없음: {msg}", "toast.updated":"{name} 업데이트됨", "toast.model_id_empty":"모델 ID는 비워둘 수 없습니다", "toast.model_id_dup":"해당 모델 ID는 이미 등록되어 있습니다", "toast.model_saved":"모델 저장됨", "toast.select_one_model":"새 모델을 하나 이상 선택하세요", "toast.added_models_one":"모델 1개 추가됨", "toast.added_models_many":"모델 {count}개 추가됨", "toast.load_routing_failed":"라우팅을 불러올 수 없음: {msg}", "toast.routing_strategy":"라우팅 전략: {name}", "toast.policy_saved":"라우팅 정책 저장됨", "toast.load_models_failed":"모델을 불러올 수 없음: {msg}", "toast.load_analytics_failed":"분석을 불러올 수 없음: {msg}", "toast.load_keys_failed":"키를 불러올 수 없음: {msg}", "toast.revoked":"{name} 해지됨", "toast.name_empty":"이름은 비워둘 수 없습니다", "toast.key_renamed":"키 이름 변경됨", "toast.name_first":"먼저 키에 이름을 지정하세요", "toast.created":"{name} 생성됨", "toast.load_security_failed":"보안 설정을 불러올 수 없음: {msg}", "toast.password_updated":"비밀번호 업데이트됨 — 다른 기기에서 로그아웃됨", "toast.load_quality_failed":"품질 점수를 불러올 수 없음: {msg}", "toast.score_range":"점수는 0에서 100 사이의 숫자여야 합니다", "toast.override_set":"{name}에 재정의 설정됨", "toast.reset":"{name} 초기화됨", "toast.aa_saved":"Artificial Analysis 키 저장됨", "toast.stored_removed":"저장된 키 제거됨", "toast.remove_key_failed":"키를 제거할 수 없음: {msg}", "toast.aa_refreshed":"Artificial Analysis 점수 새로고침됨", "toast.refresh_failed":"새로고침 실패: {msg}", "toast.load_profiles_failed":"프로필을 불러올 수 없음: {msg}", "toast.duplicated":"{name} 복제됨", "toast.now_default":"{name}이(가) 기본값이 되었습니다", "toast.deleted":"{name} 삭제됨", "toast.default_reassigned":" — 기본값이 auto가 되었습니다", "toast.saved_profile":"{name} 저장됨", "toast.file_too_large":"이 파일은 프로필 내보내기로 사용하기에 너무 큽니다.", "toast.load_integrations_failed":"통합 옵션을 불러올 수 없음: {msg}", "toast.load_mi_failed":"모델 데이터 소스를 불러올 수 없음: {msg}", "toast.source_added":"소스 추가됨", "toast.legacy_removed":"레거시 \"__custom__\" 항목 제거됨", "toast.saved_as":"{name}을(를) {slug}(으)로 저장했습니다. 아래에서 모델을 가져오세요.", "confirm.remove_provider":"{name} 키를 제거하시겠습니까? {name}으로 라우팅된 요청은 실패하기 시작합니다.", "confirm.remove_model":"모델 {name}을(를) 제거하시겠습니까?", "confirm.remove_custom":"공급자 \"{name}\" 및 해당 모델을 제거하시겠습니까?", "confirm.sign_out_others":"이 관리자의 다른 모든 브라우저에서 로그아웃하시겠습니까?", "confirm.reset_score":"{name}을(를) AA 점수로 초기화하시겠습니까?", "confirm.remove_aa_key":"저장된 Artificial Analysis 키를 제거하시겠습니까? 환경 변수 키가 있으면 다시 사용됩니다.", "confirm.change_slug":"API 식별자를 \"{old}\"에서 \"{new}\"(으)로 변경하시겠습니까?\n\nmodel: \"{old}\"을(를) 보내는 모든 클라이언트가 작동하지 않게 됩니다.", "confirm.delete_source":"이 메타데이터 소스를 삭제하시겠습니까?", "confirm.legacy_remove":"레거시 \"__custom__\" 공급자 키({prefix})를 영구 제거하시겠습니까?\n\n라우팅에 사용되지 않습니다. 필요하다면 키를 다른 곳에 저장했는지 확인하세요 — 복구할 수 없습니다.", "confirm.revoke":"\"{name}\"을(를) 해지하시겠습니까?\n\n이 키를 사용하는 클라이언트는 즉시 401을 받습니다. 되돌릴 수 없습니다 — 다시 액세스가 필요하면 새 키를 발급하세요.", "confirm.rotate":"\"{name}\"을(를) 교체하시겠습니까?\n\n동일한 제한의 대체 키가 생성되어 한 번만 표시됩니다.\n\n확인 = 지금 기존 키 해지(즉시 전환).\n취소 = 직접 해지할 때까지 기존 키 유지.", "prompt.rename_key":"키 \"{name}\"의 새 이름:", "prompt.set_score":"{name}의 수동 품질 점수 설정(0-100):", "prompt.aa_current":"현재 AA 점수: {score}", "prompt.override_note":"선택 메모(재정의하는 이유):", "auth.session_expired":"세션이 만료되었습니다. 다시 로그인하세요.", "auth.enter_creds":"사용자 이름과 비밀번호를 입력하세요.", "auth.creds_required":"사용자 이름과 비밀번호가 필요합니다.", "auth.pw_mismatch":"비밀번호가 일치하지 않습니다.", "auth.paste_token":"서버 로그의 일회용 설정 토큰을 붙여넣으세요.", "auth.signed_out":"로그아웃되었습니다.", "auth.pw_match":"비밀번호가 일치합니다.", "auth.pw_mismatch_yet":"비밀번호가 아직 일치하지 않습니다.", "auth.new_pw_mismatch":"새 비밀번호가 일치하지 않습니다.", "auth.fill_three":"세 필드를 모두 입력하세요.", "qa.connection":"Artificial Analysis 연결", "qa.test":"연결 테스트", "qa.replace":"키 교체", "qa.add":"키 추가", "qa.remove":"키 제거", "qa.last_sync":"마지막 성공 동기화", "qa.last_error":"최근 오류", "qa.never":"아직 동기화 안 됨", "qa.from_env":"환경 변수에서", "qa.saving":"저장 중…", "qa.key_hint":"이 서버에 암호화되어 저장되며 다시 표시되지 않습니다. 이전 키는 이 키가 저장될 때까지 유효합니다.", "qa.daily_limit_label":"키의 일일 한도", "qa.daily_limit_hint":"Artificial Analysis 계정 페이지에 표시된 24시간당 요청 수입니다. 비워 두면 문서상의 100/일을 사용합니다.", "qa.status.not_configured":"미설정", "qa.status.connected":"연결됨", "qa.status.invalid_key":"잘못된 키", "qa.status.rate_limited":"한도 도달", "qa.status.connection_failed":"연결 실패", "qa.status.cached":"캐시된 데이터", "pricing.legend":"가격", "pricing.allow_estimates":"Auto, 최저가 및 비용 상한에 참조 추정치 허용", "pricing.allow_estimates_help":"기본값은 꺼짐입니다. 확인된 공급자 가격만 비교하며, 참조 추정치만 있는 모델은 Auto에서 제외됩니다. 켜면 추정치 기반 결정마다 표시가 붙습니다.", "confirm.bulk_remove_models":"선택한 {count}개 모델을 제거하시겠습니까? 해당 모델로 고정된 요청은 실패합니다.", "nav.chat":"채팅", "tab.chat.title":"채팅", "tab.chat.sub":"배포된 모델과 대화하세요. SDK 트래픽처럼 라우팅, 캐시, 과금이 적용됩니다.", "ui.open_chat":"채팅 열기", "ui.open_chat_hint":"브라우저에서 배포된 모델과 채팅하세요 — SDK 트래픽과 동일한 라우팅, 캐시, 비용 추적.", "chat.new":"새 채팅", "chat.settings_title":"채팅 설정", "chat.default_title":"새 채팅", "chat.clear_history":"기록 지우기…", "chat.conversations_aria":"대화 목록", "chat.model_aria":"모델", "chat.regenerate":"응답 다시 생성", "chat.empty_title":"무엇이든 물어보세요.", "chat.empty_sub":"요청은 엔진을 통해 라우팅됩니다 — SDK 트래픽과 동일한 라우팅, 캐시, 비용 추적.", "chat.input_placeholder":"GeekCubo에게 메시지…", "chat.send":"보내기", "chat.stop":"중지", "chat.system_prompt":"시스템 프롬프트…", "chat.system_prompt_set":"시스템 프롬프트 ✓", "chat.system_ph":"당신은 유능한 어시스턴트입니다…", "chat.system_help":"비우면 채팅 기본값을 사용합니다. 대화별로 저장됩니다.", "chat.save_prompt":"프롬프트 저장", "chat.default_model":"기본 모델", "chat.default_model_help":"새 대화에 사용됩니다. 대화 내 선택기가 이를 덮어씁니다.", "chat.temperature":"온도", "chat.max_tokens":"최대 출력 토큰", "chat.default_system_prompt":"기본 시스템 프롬프트", "chat.default_system_prompt_ph":"당신은 간결한 엔지니어링 어시스턴트입니다.", "chat.default_system_help":"자체 프롬프트가 없는 대화에 적용됩니다.", "chat.save_history":"이 서버에 채팅 기록 저장", "chat.retention_days":"대화 보관 기간(일)", "chat.retention_help":"오래된 대화는 삭제됩니다. 비우면 모두 보관합니다.", "chat.font_size":"메시지 글자 크기", "chat.fs_small":"작게", "chat.fs_medium":"보통", "chat.fs_large":"크게", "chat.enter_to_send":"Enter 키로 메시지 전송", "chat.privacy_note":"대화는 이 서버의 데이터베이스에 저장됩니다. 요청은 구성한 공급자로 전송되며, SDK 트래픽과 동일합니다.", "chat.privacy_ack":"채팅 트래픽이 구성된 공급자로 전송됨을 이해했습니다", "chat.save_settings":"설정 저장", "chat.model_auto":"자동(라우터가 선택)", "chat.no_conversations":"아직 대화가 없습니다.", "chat.delete_convo_title":"이 대화 삭제", "chat.kbd_enter_send":"Enter로 전송 · Shift+Enter로 줄바꿈", "chat.kbd_ctrl_enter_send":"Ctrl+Enter로 전송 · Enter로 줄바꿈", "chat.tokens_meta":"입력 {in} · 출력 {out}", "chat.error_note":"생성이 완료 전에 중단되었습니다.", "chat.upstream_error":"업스트림 모델에서 오류가 반환되었습니다.", "toast.chat_load_failed":"채팅 데이터를 불러오지 못했습니다: {msg}", "toast.chat_failed":"채팅 요청 실패: {msg}", "toast.chat_convo_deleted":"대화가 삭제되었습니다", "toast.chat_cleared":"대화 {count}개를 지웠습니다", "toast.chat_temp_range":"온도는 0에서 2 사이여야 합니다", "toast.chat_settings_saved":"채팅 설정이 저장되었습니다", "toast.chat_open_convo":"먼저 대화를 열어주세요", "toast.chat_saved_prompt":"이 대화의 시스템 프롬프트가 저장되었습니다", "confirm.delete_conversation":"이 대화를 삭제하시겠습니까?\n\n메시지는 서버 데이터베이스에서 제거됩니다. 사용량과 비용 기록은 분석에 남습니다.", "confirm.clear_chat_history":"저장된 모든 대화를 삭제하시겠습니까?\n\n이 서버에 저장된 모든 채팅 메시지가 제거됩니다. 사용량과 비용 기록은 분석에 남습니다.", "q.ov_score":"수동 점수 (0–100)", "q.ov_note":"메모", "q.ov_model_ph":"예: openai/gpt-4o, anthropic/claude-…", "q.ov_note_ph":"AA 점수를 대체하는 이유", "q.ov_apply":"재정의 적용", "q.ov_clear":"재정의 제거", "q.ov_help":"하나 이상의 모델 id를 쉼표로 구분 — 재정의는 나열된 모든 모델에 적용됩니다. 수동 점수는 항상 AA 점수보다 우선합니다.", "toast.q_ids_required":"모델 id를 하나 이상 입력하세요", "toast.q_too_many":"일괄 처리는 최대 500개 모델 id입니다", "toast.q_bulk_set":"{count}개 모델에 재정의를 설정했습니다", "toast.q_bulk_clear":"{count}개 모델의 재정의를 제거했습니다", "providers.bulk_actions":"모델 일괄 작업", "providers.select_all":"모두 선택", "providers.selected_count":"{count}개 선택됨", "providers.bulk_capability":"기능", "providers.bulk_capability_state":"기능 상태", "providers.cap_tools":"도구", "providers.cap_vision":"비전", "providers.cap_supported":"지원", "providers.cap_unsupported":"미지원", "providers.cap_unknown":"알 수 없음", "providers.cap_catalog":"카탈로그 사용", "providers.cap_json_mode":"JSON 모드", "providers.cap_json_schema":"JSON 스키마", "providers.apply":"적용", "providers.enable":"활성화", "providers.disable":"비활성화", "providers.remove_selected":"선택 항목 제거", "providers.resolve_metadata":"확인", "toast.metadata_resolved":"메타데이터: 확인 {resolved}, 모호 {ambiguous}, 불일치 {unmatched}, 실패 {failed}.", "select.search_ph":"카탈로그 키 검색…", "providers.catalog_key_ph":"카탈로그 키 검색…", "select.remove_item":"{name} 제거", "select.use_custom":"\"{name}\" 사용", "select.no_matches":"일치하는 모델 없음", "select.more_results":"{count}개 더 — 계속 입력해 좁히세요", "q.ov_model_search_ph":"모델 검색 및 선택…", "q.ov_help_picker":"하나 이상의 모델을 검색해 선택하거나 아래 표에서 행을 체크하세요. 수동 점수는 항상 AA 점수보다 우선합니다.", "q.filter_ph":"모델 필터…", "q.select_filtered":"필터 결과 선택", "q.select_all_filtered":"필터된 모든 모델 선택", "q.deselect_all":"모두 선택 해제", "q.bulk_set":"선택 항목 점수 설정", "q.bulk_clear":"선택한 재정의 지우기", "q.select_model":"{name} 선택", "confirm.q_bulk_clear":"선택한 모델 {count}개의 수동 재정의를 지울까요?", "qa.daily_limit_short":"일일 한도", "chat.attach":"파일 첨부", "chat.attach_drop":"첨부할 파일을 놓으세요", "chat.attach_remove":"첨부 삭제", "chat.attach_unreadable":"이 파일을 읽을 수 없습니다. 파일 이름만 전송됩니다.", "chat.attach_uploading":"업로드 중…", "chat.attach_too_large":"너무 큼 (최대 {max} MB)", "toast.chat_attach_failed":"{name} 첨부 실패: {msg}", "toast.chat_attach_disabled":"이 서버에서는 첨부가 비활성화되어 있습니다.", "toast.chat_attach_too_many":"메시지당 최대 {max}개 첨부.", "toast.chat_attach_extract_failed":"{name}: 읽을 수 없음 ({msg})", "toast.chat_attach_wait":"업로드가 끝날 때까지 기다리세요.", "chat.search_toggle":"웹 검색", "chat.search_settings":"웹 검색", "chat.search_help":"활성화하면 GeekCubo가 답변 전에 웹을 검색하고 사용한 페이지를 인용합니다. 결과는 시스템 메시지로 주입되므로 어떤 모델이든 사용할 수 있습니다.", "chat.search_mode":"검색 모드", "chat.search_mode_off":"끔", "chat.search_mode_manual":"수동 (메시지마다)", "chat.search_mode_auto":"자동 (예약됨)", "chat.search_mode_help":"수동 모드는 입력창에 토글을 표시합니다. 자동은 예약되어 있으며 아직 구현되지 않았습니다.", "chat.search_backend":"검색 백엔드", "chat.search_backend_none":"백엔드 선택…", "chat.search_backend_searxng":"SearXNG (자체 호스팅)", "chat.search_backend_brave":"Brave 검색 API", "chat.search_backend_tavily":"Tavily", "chat.search_url":"SearXNG 주소", "chat.search_url_ph":"http://searxng:8080/", "chat.search_url_help":"SearXNG 인스턴스의 기본 URL입니다. 설치 프로그램의 search 프로필이 내부 네트워크에서 제공합니다.", "chat.search_api_key":"API 키", "chat.search_api_key_ph":"저장된 키를 교체할 새 키를 붙여넣으세요", "chat.search_key_clear":"저장된 키 제거", "chat.search_key_help":"이 서버에 암호화되어 저장되며 다시 표시되지 않습니다. Brave와 Tavily는 키가 필요하고 SearXNG는 필요하지 않습니다.", "chat.search_max_searches":"대화당 최대 검색 횟수", "chat.search_max_results":"검색당 결과 수", "chat.search_max_fetches":"검색당 가져올 페이지 수", "chat.search_timeout":"검색 시간 초과(초)", "chat.search_test":"연결 테스트", "chat.search_testing":"테스트 중…", "chat.search_test_ok":"{ms}ms에 {count}개 결과", "chat.search_test_failed":"검색 테스트 실패: {msg}", "chat.search_key_state_unset":"저장된 키 없음", "chat.search_key_state_set":"키 저장됨", "chat.search_key_state_undecryptable":"저장된 키의 암호를 해독할 수 없습니다", "chat.context_budget":"컨텍스트: {tokens} / {budget} 토큰", "chat.context_omitted":"이전 메시지 {count}개 생략됨", "chat.sources":"출처", "chat.search_used":"웹 검색: {backend}", "toast.search_saved":"웹 검색 설정이 저장되었습니다", "toast.search_save_failed":"웹 검색 설정을 저장하지 못했습니다: {msg}", "toast.search_test_failed":"웹 검색 테스트에 실패했습니다", "nav.local":"로컬 AI", "tab.local.title":"로컬 AI", "tab.local.sub":"내 머신의 모델을 이 라우터를 통해 제공합니다.", "local.title":"로컬 AI 연결", "local.sub":"내 머신에서 실행되는 모델로 라우팅합니다. 작은 커넥터가 이 서버로 직접 접속하므로 포트를 열거나 인바운드 터널을 둘 필요가 없습니다.", "local.refresh":"새로고침", "local.setup_button":"머신 설정", "local.feature_off_title":"서버에서 로컬 AI 연결이 꺼져 있습니다", "local.feature_off_body":"서버 환경에서 LOCAL_CONNECT_ENABLED=true를 설정하고 재시작한 뒤 이 페이지를 새로고침하세요.", "local.url_missing_title":"공개 URL이 설정되지 않았습니다", "local.url_missing_body":"커넥터가 접속할 주소(예: https://example.com)를 LOCAL_CONNECT_PUBLIC_URL로 설정하면 설치 명령과 서비스 파일이 채워집니다.", "local.settings_title":"라우팅 동작", "local.settings_sub":"로컬 모델이 자동 선택에 참여하는지, 요청이 클라우드로 폴백할 수 있는지 제어합니다.", "local.set_enabled":"라우팅에 로컬 머신 사용", "local.set_auto":"자동 선택에 로컬 모델 포함", "local.set_no_fallback":"로컬 모델 실패 시 클라우드로 폴백하지 않음", "local.settings_help":"로컬 모델은 가격이 0으로 확인되었고 머신이 승인되어 온라인일 때만 자동 선택 대상이 됩니다. \"폴백하지 않음\"을 켜면 로컬 전용 요청은 클라우드 제공자 대신 실패합니다.", "local.save_settings":"저장", "local.settings_saved":"로컬 라우팅 설정이 저장되었습니다.", "local.machines_title":"머신", "local.machines_sub":"각 머신은 하나의 커넥터입니다. 대기 중인 머신은 보이지만 승인 전에는 트래픽이 전달되지 않습니다.", "local.machines_empty":"아직 머신이 없습니다. \"머신 설정\"으로 등록 코드를 생성하세요.", "local.enrollments_title":"등록 코드", "local.enrollments_sub":"커넥터가 등록할 수 있게 하는 일회용 코드입니다. 머신이 처음 연결될 때 코드가 사용됩니다.", "local.new_code":"새 코드", "local.install_title":"커넥터 설치", "local.install_sub":"모델을 호스팅하는 머신에서 실행하세요 (Ollama, LM Studio, vLLM, llama.cpp 또는 [OI] 호환 서버).", "local.service_files":"서비스로 실행", "local.delete":"삭제", "local.never":"없음", "local.ctx_suffix":"컨텍스트", "local.ctx_unknown":"컨텍스트 알 수 없음", "local.no_models":"이 머신은 아직 모델을 보고하지 않았습니다.", "local.no_enrollments":"등록 코드가 없습니다.", "local.enroll_active":"활성", "local.enroll_used":"사용됨", "local.status_online":"온라인", "local.status_offline":"오프라인", "local.status_pending":"승인 대기", "local.status_approved":"승인됨", "local.status_revoked":"해지됨", "local.pending_note":"이 머신은 승인을 기다리고 있습니다. 모델은 표시되지만 트래픽은 전달되지 않습니다.", "local.action_approve":"승인", "local.action_discover":"모델 검색", "local.action_revoke":"해지", "local.action_rotate":"자격 증명 교체", "local.action_delete":"삭제", "local.meta_host":"호스트 이름", "local.meta_platform":"플랫폼", "local.meta_agent":"커넥터 버전", "local.meta_adapters":"어댑터", "local.meta_seen":"마지막 확인", "local.col_model":"모델", "local.col_adapter":"어댑터 유형", "local.col_context":"컨텍스트", "local.col_caps":"기능", "local.col_enabled":"사용", "local.kpi_machines":"머신", "local.kpi_online":"현재 온라인", "local.kpi_pending":"승인 대기", "local.kpi_models":"모델", "local.toast_approved":"머신이 승인되었습니다.", "local.toast_revoked":"머신이 해지되었습니다.", "local.toast_deleted":"머신이 삭제되었습니다.", "local.toast_discovered":"모델 목록이 갱신되었습니다.", "local.confirm_revoke":"이 머신을 해지할까요? 커넥터가 즉시 연결 해제되며 자격 증명을 교체할 때까지 다시 연결할 수 없습니다.", "local.confirm_delete_machine":"이 머신과 모델 목록을 삭제할까요? 이 작업은 되돌릴 수 없습니다.", "local.confirm_rotate":"이 머신의 자격 증명을 교체할까요? 실행 중인 커넥터는 재연결될 때까지 계속 동작하고, 이후 이전 자격 증명은 거부됩니다.", "local.confirm_delete_enrollment":"이 등록 코드를 삭제할까요?", "local.credential_once_title":"새 자격 증명을 지금 복사하세요", "local.credential_once_body":"한 번만 표시됩니다. 머신의 커넥터 설정에 저장하세요.", "local.wizard_title":"로컬 머신 연결", "local.wizard_close":"닫기", "local.wizard_back":"뒤로", "local.wizard_next":"다음", "local.wizard_done":"완료", "local.step1":"활성화", "local.step2":"등록 코드", "local.step3":"설치", "local.step4":"등록", "local.step5":"시작", "local.step6":"승인", "local.step7":"모델", "local.step8":"자동 라우팅", "local.w0_title":"기능 켜기", "local.w0_body":"로컬 AI 연결은 서버 측 기능입니다. 커넥터가 등록하려면 먼저 이 기능을 활성화해야 합니다.", "local.w0_ready":"기능이 활성화되었습니다. 등록 코드를 만들려면 계속하세요.", "local.w0_blocked":"이 서버에서는 기능이 비활성화되어 있습니다. LOCAL_CONNECT_ENABLED=true를 설정하고 재시작한 뒤 이 페이지를 새로고침하세요.", "local.w1_title":"등록 코드 만들기", "local.w1_body":"일회용 코드는 하나의 커넥터에만 등록을 허용합니다. 짧은 시간 후 만료됩니다.", "local.w1_name":"머신 이름 (선택 사항)", "local.w1_name_ph":"예: office-gpu", "local.w1_name_help":"목록에서 이 머신을 알아볼 라벨입니다. 나중에 이름을 바꿀 수 있습니다.", "local.w1_created":"등록 코드가 생성되었습니다", "local.w2_title":"커넥터 패키지 설치", "local.w2_body":"모델을 호스팅하는 머신에서 커넥터를 설치하세요. Python 3.11 이상이 필요합니다.", "local.w2_note":"시스템 패키지와 분리하려면 가상 환경에 설치하세요.", "local.w3_title":"머신 등록", "local.w3_body":"2단계의 코드로 등록 명령을 실행하세요. 자격 증명은 커넥터 설정 파일에 기록됩니다.", "local.w3_note":"코드는 일회용입니다. 만료되었다면 새로 만드세요.", "local.w4_title":"커넥터 시작", "local.w4_body":"연결되는 모습을 보려면 커넥터를 포그라운드에서 실행한 뒤 서비스로 전환하세요.", "local.w4_note":"커넥터는 아웃바운드 WebSocket 하나를 유지하며 자동으로 재연결합니다.", "local.w5_title":"머신이 나타날 때까지 기다리기", "local.w5_body":"커넥터가 연결되면 머신이 여기에 표시됩니다. 잠시 걸리면 새로고침하세요.", "local.w5_seen":"{name}이(가) 연결되었습니다.", "local.w5_waiting":"아직 연결된 머신이 없습니다.", "local.w5_recheck":"다시 확인", "local.w6_title":"머신 승인", "local.w6_body":"새 머신은 관리자가 승인할 때까지 대기 상태로 남습니다. 그 전에는 아무것도 전달되지 않습니다.", "local.w6_none":"아직 승인할 머신이 없습니다.", "local.w6_must_approve":"계속하기 전에 대기 중인 머신을 승인하세요.", "local.w7_title":"자동 선택에서 로컬 모델 활성화", "local.w7_body":"\"자동 선택에 로컬 모델 포함\"을 켜고 라우팅할 모델을 활성화하세요. 로컬 모델은 가격이 0으로 확인된 경우에만 자동 선택됩니다.", "local.w7_done":"설정이 완료되었습니다. 이제 로컬 모델이 공급자 및 라우팅 페이지에 표시됩니다." },
};
// Provider ids must match catalog provider ids (packages/litellm_adapter/catalog.py
// `_PROVIDER_BY_LITELLM_KEY`) and Settings env-key fields (app/config.py
// `_PROVIDERS_FROM_ENV`). Labels follow the provider's own brand spelling so
// operators recognize them without ambiguity — "xAI" with the lowercase x is
// deliberate (Grok's parent company), distinct from "Groq" the inference
// hardware company.
const PROVIDERS_KNOWN = [
  { id: "openai",      label: "OpenAI"      },
  { id: "anthropic",   label: "Anthropic"   },
  { id: "google",      label: "Google"      },
  { id: "xai",         label: "xAI (Grok)"  },
  { id: "deepseek",    label: "DeepSeek"    },
  { id: "groq",        label: "Groq"        },
  { id: "together",    label: "Together"    },
  { id: "fireworks",   label: "Fireworks"   },
];
const TAB_META = {
  overview:  { title: "tab.overview.title",  sub: "tab.overview.sub" },
  chat:      { title: "tab.chat.title",      sub: "tab.chat.sub" },
  providers: { title: "tab.providers.title", sub: "tab.providers.sub" },
  routing:   { title: "tab.routing.title",   sub: "tab.routing.sub" },
  local:     { title: "tab.local.title",     sub: "tab.local.sub" },
  analytics: { title: "tab.analytics.title", sub: "tab.analytics.sub" },
  keys:      { title: "tab.keys.title",      sub: "tab.keys.sub" },
  quality:   { title: "tab.quality.title",   sub: "tab.quality.sub" },
  security:  { title: "tab.security.title",  sub: "tab.security.sub" },
  profiles:  { title: "tab.profiles.title",  sub: "tab.profiles.sub" },
  integrations: { title: "tab.integrations.title", sub: "tab.integrations.sub" },
  intelligence: { title: "tab.intelligence.title", sub: "tab.intelligence.sub" },
};

const state = {
  // No credential is stored client-side. The administrator session is an
  // HttpOnly cookie; `csrfToken` is the only auth material in memory.
  authenticated: false,
  csrfToken: "",
  username: "",
  tab: "overview",
  providers: [],
  customProviders: [],
  legacyCustom: null,
  routing: { strategy: "balanced", preferred_models: [] },
  recent: [],
  spend: { total_microcents: 0, by_model: [] },
  latency: { by_provider: [] },
  savings: { saved_microcents: 0, savings_percent: 0 },
  models: [],
  stats: null,
  // Quality scoring (Artificial Analysis Intelligence Index + manual overrides)
  quality: { aa_index: { configured: false, source: "missing-key", matched_count: 0 }, models: [], override_count: 0 },
  qualityPreview: null,
  security: null,
  poolModels: { total: 0, models: [] },
  poolOffset: 0,
  routingAnalytics: null,
  windowDays: 7,
  lang: "python",
  locale: "en",
};
const t = (k) => I18N[state.locale]?.[k] || I18N.en[k] || k;
// Interpolating translate: tf("toast.removed_provider", {name}) — {name} is
// replaced with the value. Used for toasts/confirms/prompts that embed an id.
const tf = (k, params = {}) => {
  let s = t(k);
  for (const [key, val] of Object.entries(params)) {
    s = s.split(`{${key}}`).join(val);
  }
  return s;
};
function detectLocale() {
  const saved = localStorage.getItem(LOCALE_KEY);
  if (saved && SUPPORTED_LOCALES.includes(saved)) return saved;
  const browser = (navigator.languages?.[0] || navigator.language || "en").toLowerCase();
  const base = browser.split("-")[0];
  return SUPPORTED_LOCALES.includes(base) ? base : "en";
}
function applyI18n() {
  document.documentElement.lang = state.locale;
  document.documentElement.dir = state.locale === "ar" ? "rtl" : "ltr";
  $$("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  // Attributes cannot be reached by textContent, and an untranslated
  // placeholder or aria-label is just as visible (or audible) as body text.
  $$("[data-i18n-placeholder]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
  $$("[data-i18n-title]").forEach((el) => {
    el.title = t(el.dataset.i18nTitle);
  });
  $$("[data-i18n-aria]").forEach((el) => {
    el.setAttribute("aria-label", t(el.dataset.i18nAria));
  });
  state.qualityPicker?.refreshText();
  $("#ch-model")?.gcSelect?.refreshText();
  $("#chs-model")?.gcSelect?.refreshText();
  if (state.quality?.models?.length && $("#quality-table tbody")) updateQualityBulkState();
  if (TAB_META[state.tab]) {
    $("#page-title").textContent = t(TAB_META[state.tab].title);
    $("#page-sub").textContent = t(TAB_META[state.tab].sub);
  }
}
function bindLocalePicker() {
  const sel = $("#language-select");
  if (!sel) return;
  sel.innerHTML = SUPPORTED_LOCALES.map((lc) => `<option value="${lc}">${LOCALE_LABELS[lc]}</option>`).join("");
  sel.value = state.locale;
  sel.addEventListener("change", () => {
    state.locale = sel.value;
    localStorage.setItem(LOCALE_KEY, state.locale);
    applyI18n();
  });
}

/* ─────────────── tiny utils ─────────────── */
const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

/* ─────────────── GcSelect: searchable single/multi model picker ─────────────── */
const GC_SELECT_RENDER_LIMIT = 200;
let gcSelectSeq = 0;
class GcSelect {
  constructor(host, opts = {}) {
    this.host = host;
    this.multiple = !!opts.multiple;
    this.allowCustom = !!opts.allowCustom;
    // Optional gate for free text: only offer "Use …" when the typed value
    // passes it (e.g. a complete `namespace/model` catalog key).
    this.customAccepts = typeof opts.customAccepts === "function" ? opts.customAccepts : null;
    this.placeholderKey = opts.placeholderKey || "select.search_ph";
    this.hostOptions = opts.hostOptions || null;
    this.onChange = opts.onChange || (() => {});
    // Single-select hosts display a human label while the underlying value
    // stays stable (e.g. "auto" → "Auto (router picks)"). The dirty flag
    // tracks typed input so a label is not mistaken for a filter query.
    this.labelFor = opts.labelFor || null;
    this.dirty = false;
    this.items = [];
    this.selected = [];
    this.open = false;
    this.active = -1;
    this.filtered = [];
    this.uid = `gcs-${++gcSelectSeq}`;
    host.gcSelect = this;
    // Let callers keep using `el.value` on the host, like a native <select>.
    const valueProp = {
      configurable: true,
      get: () => this.getValue(),
      set: (v) => this.setValue(v),
    };
    Object.defineProperty(host, "value", valueProp);
    Object.defineProperty(this, "value", valueProp);
    host.classList.add("gc-select");
    host.innerHTML = `
      <div class="gc-select-field">
        <div class="gc-select-chips"></div>
        <input type="text" class="gc-select-input" role="combobox" autocomplete="off" spellcheck="false"
               autocapitalize="none" aria-autocomplete="list" aria-expanded="false" aria-controls="${this.uid}-list">
      </div>
      <ul class="gc-select-pop" id="${this.uid}-list" role="listbox" ${this.multiple ? 'aria-multiselectable="true"' : ""} hidden></ul>`;
    this.input = host.querySelector(".gc-select-input");
    this.chips = host.querySelector(".gc-select-chips");
    this.pop = host.querySelector(".gc-select-pop");
    const lbl = host.dataset.labelledby;
    if (lbl) { this.input.setAttribute("aria-labelledby", lbl); this.pop.setAttribute("aria-labelledby", lbl); }
    this.input.addEventListener("focus", () => {
      this.show();
      // Single-select shows the chosen label while idle; clear it on focus so
      // typing starts a fresh filter instead of editing the label.
      if (!this.multiple && !this.dirty) { this.input.value = ""; this.render(); }
    });
    this.input.addEventListener("click", () => { if (!this.open) this.show(); });
    this.input.addEventListener("input", () => { this.dirty = true; this.active = 0; this.show(); });
    this.input.addEventListener("keydown", (e) => this.onKey(e));
    this.pop.addEventListener("mousedown", (e) => e.preventDefault());
    this.pop.addEventListener("click", (e) => {
      const li = e.target.closest("[data-value]");
      if (li) this.pick(li.dataset.value);
    });
    this.chips.addEventListener("click", (e) => {
      const b = e.target.closest("[data-remove]");
      if (b) this.remove(b.dataset.remove);
    });
    this.onDocDown = (e) => { if (!host.contains(e.target)) this.hide(); };
    this.onReflow = () => { if (this.open) this.place(); };
    if (this.hostOptions) this.host.classList.add(...this.hostOptions.split(/\s+/).filter(Boolean));
    this.refreshText();
  }
  setItems(items) {
    this.items = items.map((it) => (typeof it === "string" ? { value: it, label: it } : it));
    if (!this.multiple) this.syncText();
    if (this.open) this.render();
  }
  labelOf(value) {
    if (!value) return "";
    if (this.labelFor) return this.labelFor(value, this.items);
    const it = this.items.find((x) => x.value === value);
    return it ? (it.label || it.value) : value;
  }
  getValue() { return this.multiple ? [...this.selected] : (this.selected[0] || ""); }
  setValue(v) {
    const arr = Array.isArray(v) ? v : (v ? [v] : []);
    this.selected = this.multiple ? [...new Set(arr)] : arr.slice(0, 1);
    this.dirty = false;
    if (this.multiple) this.renderChips();
    else this.syncText();
    if (this.open) this.render();
  }
  syncText() {
    if (this.multiple) return;
    this.dirty = false;
    this.input.value = this.labelOf(this.selected[0] || "");
  }
  refreshText() {
    this.input.placeholder = t(this.placeholderKey);
    this.syncText();
    this.renderChips();
  }
  renderChips() {
    if (!this.multiple) { this.chips.innerHTML = ""; return; }
    this.chips.innerHTML = this.selected.map((v) =>
      `<span class="gc-chip"><span class="gc-chip-text">${escapeHtml(v)}</span><button type="button" class="gc-chip-x" data-remove="${escapeHtml(v)}" aria-label="${escapeHtml(tf("select.remove_item", { name: v }))}">×</button></span>`
    ).join("");
  }
  query() { return this.input.value.trim().toLowerCase(); }
  show() {
    if (!this.open) {
      this.open = true;
      this.pop.hidden = false;
      this.input.setAttribute("aria-expanded", "true");
      document.addEventListener("mousedown", this.onDocDown);
      window.addEventListener("resize", this.onReflow);
      window.addEventListener("scroll", this.onReflow, true);
    }
    this.render();
    this.place();
  }
  hide() {
    if (!this.open) return;
    this.open = false;
    this.pop.hidden = true;
    this.input.setAttribute("aria-expanded", "false");
    this.input.removeAttribute("aria-activedescendant");
    document.removeEventListener("mousedown", this.onDocDown);
    window.removeEventListener("resize", this.onReflow);
    window.removeEventListener("scroll", this.onReflow, true);
    this.syncText();
  }
  place() {
    const r = this.input.getBoundingClientRect();
    const below = window.innerHeight - r.bottom;
    const above = r.top;
    const up = below < 200 && above > below;
    this.pop.classList.toggle("gc-select-up", up);
    const room = Math.max(120, (up ? above : below) - 16);
    this.pop.style.maxHeight = `${Math.min(240, room)}px`;
  }
  render() {
    const q = this.multiple || this.dirty ? this.query() : "";
    const all = q ? this.items.filter((it) => it.value.toLowerCase().includes(q) || (it.label || "").toLowerCase().includes(q)) : this.items;
    this.filtered = all.slice(0, GC_SELECT_RENDER_LIMIT);
    if (this.allowCustom && q && !this.items.some((it) => it.value.toLowerCase() === q)
        && (!this.customAccepts || this.customAccepts(this.input.value.trim()))) {
      this.filtered.unshift({ value: this.input.value.trim(), label: tf("select.use_custom", { name: this.input.value.trim() }), custom: true });
    }
    if (this.active >= this.filtered.length) this.active = this.filtered.length - 1;
    const sel = new Set(this.selected);
    let html = this.filtered.map((it, i) => {
      const on = sel.has(it.value);
      return `<li id="${this.uid}-o${i}" role="option" class="gc-select-opt${i === this.active ? " is-active" : ""}" aria-selected="${on}" data-value="${escapeHtml(it.value)}">${this.multiple ? `<span class="gc-select-tick" aria-hidden="true">${on ? "✓" : ""}</span>` : ""}<span class="gc-select-label">${escapeHtml(it.label || it.value)}</span>${it.hint ? `<span class="gc-select-hint">${escapeHtml(it.hint)}</span>` : ""}</li>`;
    }).join("");
    if (!this.filtered.length) html = `<li class="gc-select-empty" role="presentation">${escapeHtml(t("select.no_matches"))}</li>`;
    else if (all.length > GC_SELECT_RENDER_LIMIT) html += `<li class="gc-select-more" role="presentation">${escapeHtml(tf("select.more_results", { count: all.length - GC_SELECT_RENDER_LIMIT }))}</li>`;
    this.pop.innerHTML = html;
    if (this.active >= 0) {
      this.input.setAttribute("aria-activedescendant", `${this.uid}-o${this.active}`);
      this.pop.querySelector(".is-active")?.scrollIntoView({ block: "nearest" });
    } else {
      this.input.removeAttribute("aria-activedescendant");
    }
  }
  pick(value) {
    if (this.multiple) {
      this.selected = this.selected.includes(value) ? this.selected.filter((v) => v !== value) : [...this.selected, value];
      this.input.value = "";
      this.renderChips();
      this.render();
    } else {
      this.selected = [value];
      this.dirty = false;
      this.syncText();
      this.hide();
    }
    this.onChange(this.getValue());
    this.host.dispatchEvent(new Event("change", { bubbles: true }));
  }
  remove(value) {
    this.selected = this.selected.filter((v) => v !== value);
    this.renderChips();
    if (this.open) this.render();
    this.onChange(this.getValue());
    this.host.dispatchEvent(new Event("change", { bubbles: true }));
    this.input.focus();
  }
  onKey(e) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!this.open) { this.show(); return; }
      const n = this.filtered.length;
      if (!n) return;
      this.active = e.key === "ArrowDown" ? (this.active + 1) % n : (this.active - 1 + n) % n;
      this.render();
    } else if (e.key === "Enter") {
      if (this.open && this.active >= 0 && this.filtered[this.active]) {
        e.preventDefault();
        this.pick(this.filtered[this.active].value);
      }
    } else if (e.key === "Escape") {
      if (this.open) { e.preventDefault(); e.stopPropagation(); this.hide(); }
    } else if (e.key === "Backspace" && this.multiple && !this.input.value && this.selected.length) {
      this.remove(this.selected[this.selected.length - 1]);
    } else if (e.key === "Tab") {
      this.hide();
    }
  }
}

const fmtUsd = (mc) => {
  // Single-tenant dev workloads: a single chat completion can cost
  // ~$0.000006 (6 microcents). Default $0.00 rendering hides that
  // entirely until the operator has run hundreds of requests, which
  // makes the dashboard look broken on day 1. Lean precise on the
  // small end — a developer reading $0.000148 understands it; a
  // developer reading $0.00 thinks the meter is busted.
  const usd = (mc || 0) / 1_000_000;
  if (usd === 0) return "$0";
  if (usd < 0.001) return `$${usd.toFixed(6)}`;
  if (usd < 0.01)  return `$${usd.toFixed(5)}`;
  if (usd < 1)     return `$${usd.toFixed(3)}`;
  if (usd < 100)   return `$${usd.toFixed(2)}`;
  return `$${Math.round(usd).toLocaleString()}`;
};
const fmtNum = (n) => (n || 0).toLocaleString();
// Relative time for PAST timestamps. Future timestamps (key expiry) are
// rendered as an absolute date instead: "in 30 days" invites off-by-one
// arguments, and a negative "‑2592000s ago" is what a naive subtraction
// produces — see fmtDate below.
const fmtDate = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
};

const fmtTime = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const diffMs = Date.now() - d.getTime();
  if (diffMs < 0) return fmtDate(iso);          // future -> absolute date
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60)   return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
};

const escapeHtml = (s = "") =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;" }[c]));

// Mirror of app/routes/analytics.py:_percentile — same nearest-rank
// algorithm, including Python's banker's rounding (round-half-to-even)
// for .5 ties so client-derived percentiles match the backend
// bit-for-bit on the same sample.
function bankersRound(x) {
  const floor = Math.floor(x);
  const diff = x - floor;
  if (diff < 0.5) return floor;
  if (diff > 0.5) return floor + 1;
  return floor % 2 === 0 ? floor : floor + 1;
}
function percentile(values, pct) {
  if (!values.length) return 0;
  const s = [...values].sort((a, b) => a - b);
  const idx = Math.max(0, Math.min(s.length - 1, bankersRound((s.length - 1) * pct)));
  return Math.round(s[idx]);
}

/* ─────────────── HTTP ─────────────── */
// The console authenticates with an HttpOnly session cookie the browser sends
// automatically; JavaScript cannot read it and must not try. We only add the
// CSRF token, which is bound to that cookie server-side.
//
// `credentials: "same-origin"` is explicit: without it a fetch from an unusual
// embedding context could silently omit the cookie and every admin call would
// 401 for no visible reason.
async function api(path, opts = {}) {
  const method = (opts.method || "GET").toUpperCase();
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  if (!["GET", "HEAD", "OPTIONS"].includes(method) && state.csrfToken) {
    headers["X-CSRF-Token"] = state.csrfToken;
  }
  const r = await fetch(path, { ...opts, headers, credentials: "same-origin" });
  if (r.status === 204) return null;
  let body = null;
  try { body = await r.json(); } catch { /* ignore */ }
  if (r.status === 401 && state.authenticated && !opts.noAuthRedirect) {
    // Session expired or was revoked elsewhere (password change, CLI reset,
    // "log out other sessions", absolute/idle timeout). Drop straight to the
    // sign-in screen rather than leaving a shell that fails every request.
    handleSessionExpired();
  }
  if (!r.ok) {
    const msg = body?.error?.message || body?.detail || r.statusText || "Request failed";
    const err = new Error(msg);
    err.status = r.status;
    throw err;
  }
  return body;
}

/* ─────────────── toasts ─────────────── */
const TOAST_ICONS = {
  ok:   `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
  err:  `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
  info: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
};
function toast(msg, kind = "ok", ms = 2400) {
  const region = $("#toast-region");
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `<span class="ico">${TOAST_ICONS[kind] || TOAST_ICONS.info}</span><span>${escapeHtml(msg)}</span>`;
  region.appendChild(el);
  setTimeout(() => {
    el.classList.add("leaving");
    setTimeout(() => el.remove(), 220);
  }, ms);
}

/* ─────────────── clipboard ─────────────── */
async function copyToClipboard(text, btn) {
  try {
    await navigator.clipboard.writeText(text);
    if (btn) {
      btn.classList.add("copied");
      setTimeout(() => btn.classList.remove("copied"), 1200);
    }
    toast(t("toast.copied"), "info", 1400);
    return true;
  } catch {
    toast(t("toast.copy_blocked"), "err");
    return false;
  }
}

/* ==========================================================================
   THEME  (light / dark / system — persisted per browser)
   ========================================================================== */
const THEME_KEY = "geekcubo-theme";
const THEME_CHOICES = ["light", "system", "dark"];
const _systemDark = window.matchMedia
  ? window.matchMedia("(prefers-color-scheme: dark)")
  : { matches: false, addEventListener() {} };

function storedThemeChoice() {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return THEME_CHOICES.includes(v) ? v : "system";
  } catch {
    return "system";
  }
}

function resolvedTheme(choice) {
  if (choice === "dark") return "dark";
  if (choice === "light") return "light";
  return _systemDark.matches ? "dark" : "light";
}

function applyTheme(choice) {
  const theme = resolvedTheme(choice);
  document.documentElement.setAttribute("data-theme", theme);
  $$("[data-theme-choice]").forEach((b) => {
    const on = b.dataset.themeChoice === choice;
    b.classList.toggle("active", on);
    b.setAttribute("aria-checked", String(on));
  });
  // Charts read colors from CSS custom properties at render time.
  if (state.authenticated && typeof renderAnalytics === "function") {
    try { renderAnalytics(); } catch { /* not yet loaded */ }
  }
}

function setThemeChoice(choice) {
  if (!THEME_CHOICES.includes(choice)) return;
  try { localStorage.setItem(THEME_KEY, choice); } catch { /* private mode */ }
  applyTheme(choice);
}

/** Flip between light and dark, ignoring "system" (used by the compact toggle). */
function cycleTheme() {
  const current = document.documentElement.getAttribute("data-theme");
  setThemeChoice(current === "dark" ? "light" : "dark");
}

function bindTheme() {
  applyTheme(storedThemeChoice());
  $$("[data-theme-choice]").forEach((b) =>
    b.addEventListener("click", () => setThemeChoice(b.dataset.themeChoice))
  );
  $("#auth-theme-btn")?.addEventListener("click", cycleTheme);
  // Follow the OS while the user has chosen "system".
  _systemDark.addEventListener?.("change", () => {
    if (storedThemeChoice() === "system") applyTheme("system");
  });
}

/** Read a CSS custom property (for chart/series colors that must track the theme). */
function cssVar(name, fallback = "") {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

/* ==========================================================================
   AUTH  (administrator session)
   ==========================================================================
   Three states, driven by the server:

     /api/auth/status   { initialized }  — is there an administrator yet?
     /api/auth/me       200 | 401        — is this browser signed in?
     /api/auth/setup    needs a one-time token printed by the server
     /api/auth/login    username + password -> HttpOnly session cookie

   Nothing sensitive is kept in localStorage. The session lives in an
   HttpOnly cookie; only the CSRF token is held in memory, and that is
   useless without the cookie.
   ========================================================================== */
function showAuthView(which) {
  $("#auth-gate").hidden = false;
  $("#app-shell").hidden = true;
  ["#checking-view", "#login-view", "#setup-view"].forEach((sel) => {
    const el = $(sel);
    if (el) el.hidden = sel !== which;
  });
  if (which === "#login-view") $("#login-username")?.focus();
  if (which === "#setup-view") $("#setup-username")?.focus();
}

function setAuthStatus(sel, msg, kind) {
  const el = $(sel);
  if (!el) return;
  el.textContent = msg || "";
  el.classList.remove("ok", "err");
  if (kind) el.classList.add(kind);
}

function setBusy(sel, busy, busyLabel) {
  const btn = $(sel);
  if (!btn) return;
  if (busy) {
    btn.dataset.label = btn.dataset.label || btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner" aria-hidden="true"></span> ${busyLabel || "Working…"}`;
  } else if (btn.dataset.label) {
    btn.disabled = false;
    btn.innerHTML = btn.dataset.label;
    delete btn.dataset.label;
  }
}

async function fetchAuthStatus() {
  try {
    const r = await fetch("/api/auth/status", { credentials: "same-origin" });
    if (!r.ok) return { initialized: true };
    return await r.json();
  } catch {
    return { initialized: true };
  }
}

async function fetchSession() {
  try {
    const r = await fetch("/api/auth/me", { credentials: "same-origin" });
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}

function applySession(session) {
  state.authenticated = true;
  state.csrfToken = session.csrf_token || "";
  state.username = session.username || "Administrator";
  renderAccountMenu();
}

function clearSessionState() {
  state.authenticated = false;
  state.csrfToken = "";
  state.username = "";
}

function renderAccountMenu() {
  const name = state.username || "Administrator";
  const initial = (name.trim()[0] || "A").toUpperCase();
  if ($("#account-username")) $("#account-username").textContent = name;
  if ($("#account-avatar")) $("#account-avatar").textContent = initial;
  if ($("#account-menu-name")) $("#account-menu-name").textContent = name;
}

function renderPasswordPolicy(hint) {
  // The server's hint is English ("Minimum 8 characters"). Writing it over the
  // element would erase the translation applyI18n just put there, so the
  // translated string wins whenever it states the same minimum. Only a hint
  // carrying a DIFFERENT length (an operator changed the policy) replaces it —
  // a correct English number beats a stale translated one.
  if (!hint) return;
  const serverMin = (hint.match(/\d+/) || [])[0];
  const localized = t("auth.min_password");
  const localizedMin = (localized.match(/[\d٠-٩]+/) || [])[0];
  const toAscii = (s) => s && s.replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660));
  const text = serverMin && toAscii(localizedMin) === serverMin ? localized : hint;
  if ($("#setup-policy")) $("#setup-policy").textContent = text;
  if ($("#pw-policy")) $("#pw-policy").textContent = text;
}

function rememberReturnTab() {
  // A deep link (#quality, /routing) should survive the sign-in round trip.
  // Kept in sessionStorage so it is per-tab and dies with it.
  const fromHash = (location.hash || "").replace("#", "");
  const fromPath = location.pathname.replace(/^\/+|\/+$/g, "");
  const wanted = TAB_META[fromHash] ? fromHash : TAB_META[fromPath] ? fromPath : null;
  if (wanted && wanted !== "overview") {
    try { sessionStorage.setItem("geekcubo-return-tab", wanted); } catch { /* private mode */ }
  }
}

function consumeReturnTab() {
  try {
    const t = sessionStorage.getItem("geekcubo-return-tab");
    if (t) {
      sessionStorage.removeItem("geekcubo-return-tab");
      if (TAB_META[t]) return t;
    }
  } catch { /* private mode */ }
  return null;
}

async function bootAuth() {
  showAuthView("#checking-view");
  rememberReturnTab();

  // Ask for the session FIRST. /api/auth/me is the single request that answers
  // "can I show the dashboard?"; the previous order paid a full extra round
  // trip (/status, then /me) before the shell could appear, which is why a
  // refresh lingered on the splash.
  const session = await fetchSession();
  if (session) {
    applySession(session);
    showShell();
    return;
  }

  // Not signed in: now find out whether this install even has an
  // administrator yet, so the right screen is shown.
  const status = await fetchAuthStatus();
  renderPasswordPolicy(status.password_policy);

  if (!status.initialized) {
    showAuthView("#setup-view");
    return;
  }
  showAuthView("#login-view");
}

function showShell() {
  $("#auth-gate").hidden = true;
  $("#app-shell").hidden = false;
  renderAccountMenu();
  pollHealth();

  // Show the shell and the active panel BEFORE any data lands. Waiting on every
  // optional endpoint (analytics, quality, model data) meant a refresh sat on
  // the splash for as long as the slowest one took.
  renderEndpointControl();
  const initial = state.tab && TAB_META[state.tab] ? state.tab : "overview";
  setTab(initial, { load: false });

  // Independent, already-failing-silently loads. Each renders its own panel the
  // moment it resolves, so one slow endpoint cannot hold up the rest.
  loadStats().then(() => { renderOverview(); syncOnboarding(); });
  loadProviders().then(renderProviders);
  loadCustomProviders().then(renderCustomProviders);
  loadRouting().then(renderRouting);
  loadKeys().then(renderKeys);
  loadModels().then(() => { renderQuickstart(); renderOverview(); });
  loadAnalytics().then(renderAnalytics);
  if (initial === "routing") loadPoolModels().then(renderPoolTable);
  if (initial === "quality") refreshQualityPage();
  // Panels with no boot-time loader above (a deep link or reload straight
  // onto them). bindTabs() only selects the tab, because it runs before the
  // session is known.
  if (initial === "chat") initChatTab();
  if (initial === "security") loadSecurity().then(renderSecurity);
  if (initial === "profiles") loadProfiles().then(renderProfiles);
  if (initial === "local") loadLocalConnect().then(renderLocalConnect);
  if (initial === "integrations") loadIntegrationData().then(renderIntegrations);
  if (initial === "intelligence") loadIntelligence().then(renderIntelligence);
}

function handleSessionExpired() {
  // Only a real session loss does this. A 401 while signed out (the auth probe
  // itself) and a 403 (wrong credential class) are not expiries, and a 500 is
  // a server fault — none of them should swap the page for the login screen.
  if (!state.authenticated) return;
  clearSessionState();
  closeAccountMenu();
  showAuthView("#login-view");
  setAuthStatus("#login-status", t("auth.session_expired"), "err");
}

async function doLogin(e) {
  e.preventDefault();
  const username = $("#login-username").value.trim();
  const password = $("#login-password").value;
  if (!username || !password) {
    setAuthStatus("#login-status", t("auth.enter_creds"), "err");
    return;
  }
  setAuthStatus("#login-status", "");
  setBusy("#login-submit", true, "Signing in…");
  try {
    const r = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ username, password }),
    });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) {
      setAuthStatus("#login-status", body?.detail || body?.error?.message || "Sign-in failed.", "err");
      return;
    }
    $("#login-password").value = "";
    applySession(body);
    showShell();
    const wanted = consumeReturnTab();
    if (wanted) setTab(wanted);
    toast(tf("toast.signed_in", {name: body.username}), "ok");
  } catch (err) {
    setAuthStatus("#login-status", `Could not reach the server: ${err.message}`, "err");
  } finally {
    setBusy("#login-submit", false);
  }
}

async function doSetup(e) {
  e.preventDefault();
  const username = $("#setup-username").value.trim();
  const password = $("#setup-password").value;
  const confirm_password = $("#setup-password-confirm").value;
  const setup_token = $("#setup-token").value.trim();
  if (!username || !password) {
    setAuthStatus("#setup-status", t("auth.creds_required"), "err");
    return;
  }
  if (password !== confirm_password) {
    setAuthStatus("#setup-status", t("auth.pw_mismatch"), "err");
    return;
  }
  if (!setup_token) {
    setAuthStatus("#setup-status", t("auth.paste_token"), "err");
    return;
  }
  setAuthStatus("#setup-status", "");
  setBusy("#setup-submit", true, "Creating account…");
  try {
    const r = await fetch("/api/auth/setup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ username, password, confirm_password, setup_token }),
    });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) {
      setAuthStatus("#setup-status", body?.detail || body?.error?.message || "Setup failed.", "err");
      return;
    }
    $("#setup-password").value = "";
    $("#setup-password-confirm").value = "";
    $("#setup-token").value = "";
    applySession(body);
    showShell();
    const wanted = consumeReturnTab();
    if (wanted) setTab(wanted);
    toast(tf("toast.admin_created", {name: body.username}), "ok");
  } catch (err) {
    setAuthStatus("#setup-status", `Could not reach the server: ${err.message}`, "err");
  } finally {
    setBusy("#setup-submit", false);
  }
}

async function doLogout() {
  closeAccountMenu();
  try {
    await api("/api/auth/logout", { method: "POST" });
  } catch {
    /* the session may already be gone — clearing local state is still right */
  }
  clearSessionState();
  state.providers = [];
  state.customProviders = [];
  state.keys = [];
  showAuthView("#login-view");
  setAuthStatus("#login-status", t("auth.signed_out"), "ok");
  toast(t("toast.signed_out"), "info");
}

function bindAuth() {
  $("#login-form")?.addEventListener("submit", doLogin);
  $("#setup-form")?.addEventListener("submit", doSetup);

  // Show/hide password controls.
  const pair = [
    ["#login-password-toggle", "#login-password"],
    ["#setup-password-toggle", "#setup-password"],
  ];
  pair.forEach(([btnSel, inputSel]) => {
    $(btnSel)?.addEventListener("click", () => {
      const input = $(inputSel);
      input.type = input.type === "password" ? "text" : "password";
    });
  });

  // Live "passwords match" feedback while typing the confirmation.
  const confirm = $("#setup-password-confirm");
  confirm?.addEventListener("input", () => {
    const pw = $("#setup-password").value;
    if (!confirm.value) { setAuthStatus("#setup-status", ""); return; }
    if (pw === confirm.value) setAuthStatus("#setup-status", t("auth.pw_match"), "ok");
    else setAuthStatus("#setup-status", t("auth.pw_mismatch_yet"), "err");
  });

  // Account dropdown.
  const btn = $("#account-btn");
  const menu = $("#account-dropdown");
  btn?.addEventListener("click", (e) => {
    e.stopPropagation();
    const open = menu.hidden;
    menu.hidden = !open;
    btn.setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("click", (e) => {
    if (!menu || menu.hidden) return;
    if (!menu.contains(e.target) && !btn.contains(e.target)) closeAccountMenu();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAccountMenu();
  });
  $("#logout-btn")?.addEventListener("click", doLogout);
}

function closeAccountMenu() {
  const menu = $("#account-dropdown");
  const btn = $("#account-btn");
  if (menu) menu.hidden = true;
  if (btn) btn.setAttribute("aria-expanded", "false");
}

/* ==========================================================================
   TABS / ROUTING
   ========================================================================== */
function setTab(tab, { load = true } = {}) {
  if (!TAB_META[tab]) return;
  state.tab = tab;
  history.replaceState(null, "", `#${tab}`);
  $$("#tabs .nav-item").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  $$(".panel").forEach((p) => p.classList.remove("active"));
  $(`#panel-${tab}`).classList.add("active");
  $("#page-title").textContent = t(TAB_META[tab].title);
  $("#page-sub").textContent = t(TAB_META[tab].sub);
  // `load: false` is used at boot, where the caller is already fetching
  // everything — otherwise the first paint fired every request twice.
  if (!load) return;
  // refresh the tab's data so it's fresh-on-view
  if (tab === "chat") initChatTab();
  if (tab === "analytics") loadAnalytics().then(renderAnalytics);
  if (tab === "providers") {
    Promise.all([loadProviders(), loadCustomProviders(), loadStats()]).then(() => {
      renderProviders();
      renderCustomProviders();
    });
  }
  if (tab === "keys")      loadKeys().then(renderKeys);
  if (tab === "overview")  {
    Promise.allSettled([loadStats(), loadProviders(), loadCustomProviders()]).then(() => {
      renderOverview();
    });
  }
  if (tab === "security") {
    loadSecurity().then(renderSecurity);
  }
  if (tab === "routing") {
    Promise.all([loadRouting(), loadPoolModels()]).then(() => {
      renderRouting();
      renderPoolTable();
    });
  }
  if (tab === "profiles") loadProfiles().then(renderProfiles);
  if (tab === "local") loadLocalConnect().then(renderLocalConnect);
  if (tab === "integrations") loadIntegrationData().then(renderIntegrations);
  if (tab === "intelligence") loadIntelligence().then(renderIntelligence);
  if (tab === "quality") refreshQualityPage();
}

function bindTabs() {
  $$("#tabs .nav-item").forEach((b) =>
    b.addEventListener("click", () => setTab(b.dataset.tab))
  );
  // Inline anchor "go to tab" links
  document.addEventListener("click", (e) => {
    const t = e.target.closest("[data-go-tab]");
    if (t) {
      e.preventDefault();
      setTab(t.dataset.goTab);
    }
  });
  // Initial tab from hash, or from a deep-link path (/providers is served the
  // same shell by the server — see app/main.py providers_page).
  const fromHash = (location.hash || "").replace("#", "");
  const fromPath = location.pathname.replace(/^\/+|\/+$/g, "");
  const initial = TAB_META[fromHash] ? fromHash : fromPath;
  // Select the tab only: this runs before bootAuth() knows whether a session
  // exists, so loading here fired every panel's requests unauthenticated.
  // For Chat that cached `attachmentLimits = {enabled:false}` from the 401
  // and hid the paperclip for the rest of the page's life. showShell()
  // loads the selected tab once the session is confirmed.
  if (TAB_META[initial]) setTab(initial, { load: false });
}

/* ==========================================================================
   PROVIDERS
   ========================================================================== */
async function loadProviders() {
  try {
    const data = await api("/v1/providers");
    const all = data.providers || [];
    // "__custom__" is never a real provider (see renderLegacyCustomBanner).
    // Keep it out of the normal table and quick-add logic; it gets its own
    // migration notice instead of masquerading as a configured provider.
    state.legacyCustom = all.find((p) => p.provider === CUSTOM_OPTION && p.source === "db") || null;
    state.providers = all.filter((p) => p.provider !== CUSTOM_OPTION);
  } catch (e) {
    toast(tf("toast.load_providers_failed", {msg: e.message}), "err");
  }
}

/** Notice + operator-controlled cleanup for a legacy provider_keys row named
 *  "__custom__". Created by the pre-Phase-1 bundle; it holds a real API key
 *  but no name or base URL, so routing can never use it. We do NOT migrate
 *  the key automatically (we don't know which URL it belongs to and must not
 *  move credentials without consent) and we do NOT delete it silently. */
function renderLegacyCustomBanner() {
  const banner = $("#legacy-custom-banner");
  const body = $("#legacy-custom-body");
  if (!banner || !body) return;
  const legacy = state.legacyCustom;
  if (!legacy) { banner.hidden = true; return; }
  banner.hidden = false;
  body.textContent =
    `A provider key named "__custom__" (key ${legacy.key_prefix || "…"}) was saved by an earlier dashboard ` +
    `version that did not support named custom providers. It has no provider name or base URL, so it is ` +
    `NOT used for routing. To use this key, re-create it as a named provider using ` +
    `"Others (OpenAI format)" ` +
    `(you will need to paste the key again — it is never shown). The legacy entry is kept until you remove it.`;
}

function bindLegacyCustomBanner() {
  const resave = $("#legacy-custom-resave");
  if (resave) {
    resave.addEventListener("click", (e) => {
      e.preventDefault();
      const sel = $("#provider-name");
      sel.value = CUSTOM_OPTION;
      toggleCustomFields();
      $("#custom-provider-name")?.focus();
    });
  }
  const del = $("#legacy-custom-delete");
  if (del) {
    del.addEventListener("click", async (e) => {
      e.preventDefault();
      if (!state.legacyCustom) return;
      const ok = confirm(tf("confirm.legacy_remove", {prefix: state.legacyCustom.key_prefix || "…"}));
      if (!ok) return;
      try {
        await api(`/v1/providers/${CUSTOM_OPTION}`, { method: "DELETE" });
        toast(t("toast.legacy_removed"), "ok");
        await loadProviders();
        renderProviders();
      } catch (err) {
        toast(err.message, "err");
      }
    });
  }
}

function renderProviders() {
  const tbody = $("#providers-table tbody");
  const empty = $("#providers-empty");
  const banner = $("#providers-decrypt-banner");
  const bannerBody = $("#providers-decrypt-banner-body");
  const broken = state.providers.filter((p) => p.source === "db" && p.decryptable === false);
  if (banner && bannerBody) {
    if (broken.length) {
      const names = broken.map((p) => p.provider).join(", ");
      bannerBody.textContent =
        `${names} ${broken.length === 1 ? "is" : "are"} sealed with a different CREDENTIAL_ENCRYPTION_KEY. ` +
        `Re-save ${broken.length === 1 ? "this key" : "these keys"} below, or set CREDENTIAL_ENCRYPTION_PREVIOUS_KEY to the prior value and restart.`;
      banner.hidden = false;
    } else {
      banner.hidden = true;
    }
  }
  tbody.innerHTML = "";
  if (!state.providers.length) {
    empty.classList.add("shown");
  } else {
    empty.classList.remove("shown");
    state.providers.forEach((p) => {
      const tr = document.createElement("tr");
      tr.className = "row-in";
      // Env-sourced keys come from .env / process env, not the DB.
      // Disabling delete avoids a confusing "no-op" — the row would
      // come right back on next load because the env var is still set.
      // Operator can still PUT a DB-sourced key for the same provider
      // to override the env value (the runtime resolver picks DB > env).
      const isEnv = p.source === "env";
      const cannotDecrypt = p.source === "db" && p.decryptable === false;
      const sourceBadge = isEnv
        ? '<span class="pill muted" title="Set via .env / environment variable. Edit the env file and restart to change.">env</span>'
        : '';
      const removeBtn = isEnv
        ? `<span class="muted small" title="Remove the OPENAI_API_KEY (or equivalent) from .env and restart the server.">env-managed</span>`
        : `<button class="btn btn-ghost btn-sm btn-danger del-prov" data-prov="${escapeHtml(p.provider)}">Remove</button>`;
      const statusPill = cannotDecrypt
        ? '<span class="pill err" title="Ciphertext does not open with the current CREDENTIAL_ENCRYPTION_KEY. Re-save the key or set CREDENTIAL_ENCRYPTION_PREVIOUS_KEY and restart.">Can\'t decrypt</span>'
        : (p.is_enabled
          ? '<span class="pill ok">Enabled</span>'
          : '<span class="pill muted">Disabled</span>');
      tr.innerHTML = `
        <td><strong>${escapeHtml(p.provider)}</strong> ${sourceBadge}</td>
        <td><code>${escapeHtml(p.key_prefix || "—")}</code></td>
        <td>${statusPill}</td>
        <td class="th-actions">${removeBtn}</td>
      `;
      tbody.appendChild(tr);
    });
    $$(".del-prov").forEach((b) =>
      b.addEventListener("click", async () => {
        const prov = b.dataset.prov;
        if (!confirm(tf("confirm.remove_provider", {name: prov}))) return;
        try {
          await api(`/v1/providers/${prov}`, { method: "DELETE" });
          toast(tf("toast.removed_provider", {name: prov}), "ok");
          await Promise.all([loadProviders()]);
          renderProviders();
          renderQuickAdd();
          renderOverview();
          syncOnboarding();
        } catch (e) {
          toast(e.message, "err");
        }
      })
    );
  }
  renderQuickAdd();
  renderLegacyCustomBanner();
}

function renderQuickAdd() {
  const wrap = $("#provider-quickadd");
  if (!wrap) return;
  // Healthy DB-sourced providers are "fully configured" — disable the
  // chip so the operator doesn't accidentally re-PUT and clobber a
  // known-good key. Undecryptable DB rows stay clickable so the operator
  // can re-enter the key after a CREDENTIAL_ENCRYPTION_KEY rotation.
  // ENV-sourced providers stay clickable: clicking pre-fills the form so
  // the operator can write a DB row that overrides the env value (matches
  // the runtime resolver's DB > env precedence).
  const dbConfigured = new Set(
    state.providers
      .filter((p) => p.source === "db" && p.decryptable !== false)
      .map((p) => p.provider)
  );
  const brokenDb = new Set(
    state.providers
      .filter((p) => p.source === "db" && p.decryptable === false)
      .map((p) => p.provider)
  );
  const envConfigured = new Set(
    state.providers.filter((p) => p.source === "env").map((p) => p.provider)
  );
  wrap.innerHTML = `<span class="muted" style="font-size:12px;align-self:center;margin-right:4px">Quick-add:</span>` +
    PROVIDERS_KNOWN.map((p) => {
      const isDb = dbConfigured.has(p.id);
      const isBroken = brokenDb.has(p.id);
      const isEnv = envConfigured.has(p.id);
      const cls = isDb ? "configured" : (isBroken ? "needs-resave" : (isEnv ? "env-override" : ""));
      const disabled = isDb ? "disabled" : "";
      const title = isBroken
        ? `${p.label} is stored but cannot be decrypted. Click to re-enter the key.`
        : (isEnv
          ? `${p.label} is set via .env. Click to override with a custom key (writes a DB row that takes precedence).`
          : "");
      const suffix = isBroken
        ? " <span class=\"small muted\">(re-enter)</span>"
        : (isEnv ? " <span class=\"small muted\">(env, override)</span>" : "");
      return `<button class="chip ${cls}" data-prov-pick="${p.id}" ${disabled} ${title ? `title="${escapeHtml(title)}"` : ""}>
        ${escapeHtml(p.label)}${suffix}
      </button>`;
    }).join("");
  $$("[data-prov-pick]").forEach((b) =>
    b.addEventListener("click", () => {
      const sel = $("#provider-name");
      sel.value = b.dataset.provPick;
      toggleCustomFields();
      $("#provider-key").focus();
    })
  );
}

function bindProviderForm() {
  $("#provider-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const provider = $("#provider-name").value;
    // Never write a provider_keys row named "__custom__". That synthetic id
    // is a UI sentinel, not a provider: it has no catalog entry, so routing
    // can never use the key, and the row is a puzzling credential to explain
    // later. The custom form owns that path now.
    if (provider === CUSTOM_OPTION) {
      showCustomFormError("Select Others (OpenAI format) to create a named custom provider.");
      return;
    }
    const apiKeyVal = $("#provider-key").value.trim();
    if (!apiKeyVal) {
      toast(t("toast.api_key_empty"), "err");
      return;
    }
    try {
      await api(`/v1/providers/${provider}`, {
        method: "PUT",
        body: JSON.stringify({ api_key: apiKeyVal }),
      });
      $("#provider-key").value = "";
      toast(tf("toast.saved_provider", {name: provider}), "ok");
      await Promise.all([loadProviders()]);
      renderProviders();
      renderOverview();
      syncOnboarding();
    } catch (err) {
      toast(err.message, "err");
    }
  });
}

/* ==========================================================================
   CUSTOM PROVIDERS (OpenAI Format – Others)
   ========================================================================== */
const CUSTOM_OPTION = "__custom__";

/** Mirror of app/custom_providers.normalize_slug — same rules, so the slug we
 *  preview is the slug the server stores ("Apixo AI" -> "apixo-ai"). */
function slugifyProviderName(name) {
  return String(name || "")
    .trim()
    .replace(/[^a-zA-Z0-9_-]+/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase()
    .slice(0, 50)
    .replace(/-+$/g, "");
}

function showCustomFormError(msg) {
  const el = $("#custom-form-error");
  if (!el) return;
  if (!msg) {
    el.hidden = true;
    el.textContent = "";
    return;
  }
  el.hidden = false;
  el.textContent = msg;
}

/** Client-side validation with actionable messages. The server re-validates
 *  (SSRF, reserved slugs, duplicates); this only catches the obvious cases
 *  before a round-trip so the operator gets the error inline. */
function validateCustomProviderInput({ name, baseUrl, apiKey }) {
  if (!name) return "Provider Name is required (for example: Apixo).";
  if (name.length > 100) return "Provider Name must be 100 characters or fewer.";
  if (!slugifyProviderName(name)) {
    return "Provider Name must contain at least one letter or digit.";
  }
  if (!baseUrl) return "API Base URL is required (for example: https://api.example.com/v1).";
  let parsed;
  try {
    parsed = new URL(baseUrl);
  } catch {
    return "API Base URL must be a full URL, including https:// — for example https://api.example.com/v1.";
  }
  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
    return `API Base URL must start with http:// or https://, not ${parsed.protocol}`;
  }
  if (parsed.username || parsed.password) {
    return "API Base URL must not embed credentials — put the key in the API Key field.";
  }
  if (!parsed.hostname) return "API Base URL must include a host.";
  if (!apiKey) return "API Key is required.";
  return "";
}

function updateSlugHint() {
  const hint = $("#custom-slug-hint");
  if (!hint) return;
  const name = ($("#custom-provider-name")?.value || "").trim();
  const slug = slugifyProviderName(name);
  if (!name) {
    hint.textContent = "";
    hint.hidden = true;
    return;
  }
  hint.hidden = false;
  hint.textContent = slug
    ? `Internal id: ${slug} — models are addressed as ${slug}/<model-id>`
    : "Provider Name must contain at least one letter or digit.";
  hint.classList.toggle("err", !slug);
}

/** Swap the built-in provider-key form for the custom-provider form. */
function syncProviderTabs(isCustom) {
  $$("[data-provider-tab]").forEach((btn) => {
    const active = btn.dataset.providerTab === (isCustom ? "custom" : "standard");
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", active ? "true" : "false");
  });
}

function toggleCustomFields() {
  const sel = $("#provider-name");
  if (!sel) return;
  const isCustom = sel.value === CUSTOM_OPTION;
  const keyFields = $("#provider-key-fields");
  const customForm = $("#custom-provider-form");
  if (keyFields) keyFields.hidden = isCustom;
  if (customForm) customForm.hidden = !isCustom;
  syncProviderTabs(isCustom);
  // A hidden field must never block (or be submitted by) the other form.
  const builtinKey = $("#provider-key");
  if (builtinKey) builtinKey.required = false;
  if (!isCustom) showCustomFormError("");
  else ($("#custom-provider-name") || {}).focus?.();
  updateSlugHint();
}

function bindCustomProviderToggle() {
  const sel = $("#provider-name");
  if (sel) {
    sel.addEventListener("change", toggleCustomFields);
    toggleCustomFields();
  }
  // The tabs are the primary affordance; selecting one moves the underlying
  // <select> so there is still exactly one source of truth for the mode.
  $$("[data-provider-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.providerTab === "custom") {
        if (sel) sel.value = CUSTOM_OPTION;
      } else if (sel && sel.value === CUSTOM_OPTION) {
        sel.value = "openai";
      }
      toggleCustomFields();
      if (btn.dataset.providerTab === "custom") $("#custom-provider-name")?.focus();
      else $("#provider-key")?.focus();
    });
  });
  const nameInput = $("#custom-provider-name");
  if (nameInput) nameInput.addEventListener("input", updateSlugHint);
  bindCustomProviderCreate();
}

function bindCustomProviderCreate() {
  const form = $("#custom-provider-form");
  if (!form) return;
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if ($("#provider-name").value !== CUSTOM_OPTION) return;
    const name = $("#custom-provider-name").value.trim();
    const baseUrl = $("#custom-base-url").value.trim();
    const apiKey = $("#custom-api-key").value.trim();
    const problem = validateCustomProviderInput({ name, baseUrl, apiKey });
    if (problem) {
      showCustomFormError(problem);
      toast(problem, "err");
      return;
    }
    showCustomFormError("");
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.disabled = true;
    try {
      const created = await api("/v1/custom-providers", {
        method: "POST",
        body: JSON.stringify({ display_name: name, base_url: baseUrl, api_key: apiKey }),
      });
      $("#custom-api-key").value = "";
      $("#custom-provider-name").value = "";
      $("#custom-base-url").value = "";
      updateSlugHint();
      toast(
        tf("toast.saved_as", {name: created?.display_name || name, slug: created?.slug || slugifyProviderName(name)}),
        "ok"
      );
      await Promise.all([loadCustomProviders()]);
      renderCustomProviders();
      renderOverview();
      syncOnboarding();
      // Keep the dropdown on the custom option so the operator can add a
      // second provider right away, and focus the empty name field.
      toggleCustomFields();
      $("#custom-provider-name")?.focus();
    } catch (err) {
      // Server-side 422/409 messages are already actionable (reserved slug,
      // duplicate provider, SSRF rejection) — show them inline, not only as
      // a toast that disappears.
      showCustomFormError(err.message);
      toast(err.message, "err");
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });
}

async function loadCustomProviders() {
  try {
    const data = await api("/v1/custom-providers");
    state.customProviders = data.providers || [];
  } catch (e) {
    toast(tf("toast.load_custom_failed", {msg: e.message}), "err");
  }
}

function _cpStatusPill(p) {
  if (p.decryptable === false) {
    return '<span class="pill err" title="Stored key cannot be decrypted with the current CREDENTIAL_ENCRYPTION_KEY. Re-save the key.">Can\'t decrypt</span>';
  }
  return p.is_enabled
    ? '<span class="pill ok">Enabled</span>'
    : '<span class="pill muted">Disabled</span>';
}

function _cpAutoPill(p) {
  return p.eligible_for_auto
    ? '<span class="pill ok" title="Models participate in model=auto routing.">auto-eligible</span>'
    : '<span class="pill muted" title="Models are reachable by pinning slug/model-id, but not auto-selected.">pinned only</span>';
}
// Registered-model view state per provider (search + page), so large
// catalogs render one page at a time instead of hundreds of rows.
const MODEL_PAGE = 25;
const MODEL_VIEW = {};

/* Catalog-identity status: one vocabulary for the registered-models table,
 * the provider summary and the discovery list. Short visible label, full
 * explanation in the tooltip AND the accessible name (title alone is not
 * read by every screen reader). */
const MATCH_STATUS = {
  resolved:  { cls: "ok",    label: "Resolved",   help: "One catalog entry matched; context, capabilities and reference prices are inherited from it." },
  partial:   { cls: "warn",  label: "Partial",   help: "A catalog entry matched but is missing context, a reference price or tool support. Missing fields stay Unknown." },
  ambiguous: { cls: "warn",  label: "Ambiguous", help: "Several catalog entries use this id (resellers, other vendors). Nothing is inherited until you pick the right key." },
  unmatched: { cls: "muted", label: "Unmatched",  help: "No catalog entry uses this id (custom, renamed or modified model). Capabilities and prices stay Unknown unless you set them." },
};
const MATCH_ORDER = ["resolved", "partial", "ambiguous", "unmatched"];

/** A complete catalog key looks like `namespace/model`, no spaces. */
function _isFullCatalogKey(value) {
  return /^[a-z0-9][\w.@:-]*\/[^\s/][^\s]*$/i.test(value || "");
}

function _matchStatusOf(m) {
  return m.match_status || (m.catalog_key ? "resolved" : (m.match_confidence === "ambiguous" ? "ambiguous" : "unmatched"));
}

function _matchBadge(status, extra = "") {
  const s = MATCH_STATUS[status] || { cls: "muted", label: status || "unknown", help: "" };
  const tip = extra ? `${s.help} ${extra}` : s.help;
  return `<span class="pill ${s.cls} match-badge" data-match="${escapeHtml(status)}" title="${escapeHtml(tip)}" aria-label="Catalog: ${escapeHtml(s.label)}. ${escapeHtml(tip)}">${escapeHtml(s.label)}</span>`;
}

/** Counts by status as compact pills. With `filterFor`, each pill is a
 *  toggle button that filters the list it summarises. */
function _matchCounts(counts, { filterFor = null, active = "" } = {}) {
  return MATCH_ORDER.filter((s) => counts[s]).map((s) => {
    const meta = MATCH_STATUS[s];
    const text = `${counts[s]} ${meta.label.toLowerCase()}`;
    if (!filterFor) {
      return `<span class="pill ${meta.cls}" title="${escapeHtml(meta.help)}">${escapeHtml(text)}</span>`;
    }
    const on = active === s;
    return `<button type="button" class="pill ${meta.cls} match-filter${on ? " is-on" : ""}" data-match-filter="${escapeHtml(s)}" data-match-scope="${escapeHtml(filterFor)}" aria-pressed="${on}" title="${escapeHtml(on ? "Show all" : `Show only: ${meta.help}`)}">${escapeHtml(text)}</button>`;
  }).join(" ");
}

// One delegated handler for every catalog-status filter (registered table
// and discovery list); both re-render in place, so per-render binding would
// stack duplicate listeners.
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-match-filter]");
  if (!btn) return;
  const scope = btn.dataset.matchScope || "";
  const want = btn.dataset.matchFilter || "";
  if (scope.startsWith("fetch:")) {
    const pid = scope.slice(6);
    const fs = FETCH_STATE[pid];
    if (!fs) return;
    fs.status = fs.status === want ? "" : want;
    renderFetchPanel(pid);
    bindFetchPanel(pid);
    return;
  }
  const v = _modelView(scope);
  v.status = v.status === want ? "" : want;
  v.page = 0;
  _rerenderModelsTable(scope);
});

function _modelView(pid) {
  if (!MODEL_VIEW[pid]) MODEL_VIEW[pid] = { q: "", page: 0, status: "" };
  return MODEL_VIEW[pid];
}

function _yes(v, label) {
  return v ? `<span class="cap-yes" aria-label="${label}: yes">Yes</span>` : `<span class="muted" aria-label="${label}: no">—</span>`;
}

const MODEL_SELECT = {};

function _selection(pid) {
  if (!MODEL_SELECT[pid]) MODEL_SELECT[pid] = new Set();
  return MODEL_SELECT[pid];
}

function _capState(m, key) {
  return (m.capabilities && m.capabilities[key]) || "unknown";
}

function _capSelect(m, key, label) {
  const state = _capState(m, key);
  const opts = ["supported", "unsupported", "unknown"].map((v) =>
    `<option value="${v}" ${v === state ? "selected" : ""}>${v === "supported" ? "Supported" : v === "unsupported" ? "Unsupported" : "Unknown"}</option>`
  ).join("") + (m.capability_sources && m.capability_sources[key] === "administrator_override"
    ? `<option value="catalog">${escapeHtml(t("providers.cap_catalog"))}</option>` : "");
  return `<select class="cp-cap-select" data-cp-cap="${key}" data-model-row="${escapeHtml(m.id)}" aria-label="${label} capability">${opts}</select>`;
}

function _cpProvLine(kind, source, { stale = false, override = false } = {}) {
  const src = escapeHtml(source || "unknown");
  return `<div class="cp-prov muted small" data-prov="${kind}" title="${override ? "Set by operator override" : `Persisted source of the ${kind} value`}">via ${src}${stale ? ' <span class="pill muted" title="Cached source is stale">stale</span>' : ""}${override ? ' <span class="pill muted" title="Operator override — catalog refreshes never replace it">override</span>' : ""}</div>`;
}

function _cpModelProvenance(m) {
  const meta = m.metadata && typeof m.metadata === "object" ? m.metadata : {};
  const caps = meta.capabilities && typeof meta.capabilities === "object" ? meta.capabilities : {};
  const ctx = meta.context && typeof meta.context === "object" ? meta.context : {};
  const ref = meta.reference && typeof meta.reference === "object" ? meta.reference : {};
  const manual = meta.manual && typeof meta.manual === "object" ? meta.manual : {};
  const out = {};
  for (const key of ["tools", "vision", "json_mode", "json_schema"]) {
    const c = caps[key] && typeof caps[key] === "object" ? caps[key] : {};
    out[key] = _cpProvLine(key, c.source || (m.capability_sources || {})[key], { stale: !!c.stale, override: !!c.override });
  }
  out.context = _cpProvLine("context", ctx.source, { stale: !!ctx.stale, override: !!ctx.manual });
  const refStale = !!(ref.stale || m.reference_stale);
  const refSrc = ref.source || m.reference_source;
  out.reference_input = _cpProvLine("reference_input", refSrc, { stale: refStale, override: !!manual.reference });
  out.reference_output = _cpProvLine("reference_output", refSrc, { stale: refStale, override: !!manual.reference });
  const custom = meta.custom && typeof meta.custom === "object" ? meta.custom : {};
  const customConfigured = m.price_state === "custom";
  const customSrc = custom.source || (customConfigured ? "administrator" : null);
  out.custom_input = _cpProvLine("custom_input", customSrc, { override: customConfigured });
  out.custom_output = _cpProvLine("custom_output", customSrc, { override: customConfigured });
  return out;
}

function _cpModelsTable(p) {
  if (!p.models || !p.models.length) {
    return '<p class="cp-meta muted">No models registered yet. Use Fetch Available Models, or add one manually below.</p>';
  }
  const view = _modelView(p.id);
  const selected = _selection(p.id);
  selected.forEach((id) => { if (!p.models.some((m) => m.id === id)) selected.delete(id); });
  const needle = view.q.trim().toLowerCase();
  const filtered = p.models.filter((m) =>
    (!needle || m.model_id.toLowerCase().includes(needle)
      || (m.display_name || "").toLowerCase().includes(needle))
    && (!view.status || _matchStatusOf(m) === view.status));
  const selectedFiltered = filtered.filter((m) => selected.has(m.id));
  const allFilteredSelected = filtered.length > 0 && selectedFiltered.length === filtered.length;
  const pages = Math.max(1, Math.ceil(filtered.length / MODEL_PAGE));
  if (view.page >= pages) view.page = pages - 1;
  const slice = filtered.slice(view.page * MODEL_PAGE, (view.page + 1) * MODEL_PAGE);
  const price = (v) => (v == null ? '<span class="muted" title="Unknown — never treated as free">unknown</span>' : `$${Number(v).toFixed(2)}`);
  const rows = slice.map((m) => {
    const prov = _cpModelProvenance(m);
    const refProv = prov.reference_input || prov.reference_output;
    const ref = m.reference_input_cost_per_million != null || m.reference_output_cost_per_million != null
      ? `${price(m.reference_input_cost_per_million)} / ${price(m.reference_output_cost_per_million)}${refProv}${m.reference_stale ? ' <span class="pill muted" title="Cached source is stale">stale</span>' : ""}`
      : `<span class="muted" title="No trusted vendor reference match">unknown</span>${refProv}`;
    const status = _matchStatusOf(m);
    const cands = m.match_candidates || [];
    const total = (m.metadata?.identity?.candidate_total) || cands.length;
    const matchDetail = m.catalog_key
      ? `Key: ${m.catalog_key}.`
      : status === "ambiguous" ? `${total} catalog entries share this id.` : "";
    const needsKey = (status === "ambiguous" || status === "unmatched") && cands.length > 0;
    const catalogPicker = needsKey
      ? `<div class="cp-catalog-select" data-cp-catalog="${escapeHtml(m.id)}" data-candidates="${escapeHtml((m.match_candidates || []).join("\n"))}" aria-label="Catalog key for ${escapeHtml(m.model_id)}"></div>`
      : (m.catalog_key ? `<button type="button" class="btn btn-ghost btn-sm cp-catalog-clear" data-cp-catalog-clear="${escapeHtml(m.id)}" title="Clear the catalog override and re-resolve">clear key</button>` : "");
    return `
    <tr data-model-row="${escapeHtml(m.id)}" class="${m.is_enabled === false ? "cp-model-disabled" : ""}">
      <td><input type="checkbox" class="cp-model-check" data-cp-check="${escapeHtml(m.id)}" ${selected.has(m.id) ? "checked" : ""} aria-label="Select ${escapeHtml(m.model_id)}"></td>
      <td><code>${escapeHtml(p.slug)}/${escapeHtml(m.model_id)}</code>${m.display_name && m.display_name !== m.model_id ? `<div class="muted small">${escapeHtml(m.display_name)}</div>` : ""}
        <div class="cp-match-line muted small">${_matchBadge(status, matchDetail)}${m.catalog_key ? ` <code class="cp-match-key">${escapeHtml(m.catalog_key)}</code>` : status === "ambiguous" ? ` <span>${escapeHtml(`pick 1 of ${total}`)}</span>` : ""}</div>
        ${catalogPicker ? `<div class="cp-catalog-pick">${catalogPicker}</div>` : ""}</td>
      <td>${m.context_length ? m.context_length.toLocaleString() : '<span class="muted" title="Unknown">—</span>'}${prov.context}${m.max_output_tokens ? `<div class="muted small" title="Maximum output tokens reported by the provider">max out ${Number(m.max_output_tokens).toLocaleString()}</div>` : ""}</td>
      <td>${_capSelect(m, "tools", "Tools")}${prov.tools}</td>
      <td>${_capSelect(m, "vision", "Vision")}${prov.vision}</td>
      <td>${_capSelect(m, "json_mode", "JSON mode")}${prov.json_mode}</td>
      <td>${_capSelect(m, "json_schema", "JSON schema")}${prov.json_schema}</td>
      <td>${ref}</td>
      <td>${m.price_state === "custom" ? `${price(m.input_cost_per_million)} / ${price(m.output_cost_per_million)}${prov.custom_input}` : `<span class="muted" title="No confirmed custom-provider rate configured">unknown</span>${prov.custom_input}`}</td>
      <td><label class="checkline" title="Disabled models stay registered but are not deployed or Auto-selected"><input type="checkbox" class="cp-model-enabled" data-cp-enable="${escapeHtml(m.id)}" ${m.is_enabled !== false ? "checked" : ""}> ${m.is_enabled !== false ? "Enabled" : "Disabled"}</label></td>
      <td class="th-actions">
        <button class="btn btn-ghost btn-sm cp-model-details" data-cp="${escapeHtml(p.id)}" data-model="${escapeHtml(m.model_id)}" aria-expanded="false">Details</button>
        <button class="btn btn-ghost btn-sm cp-model-edit" data-cp="${escapeHtml(p.id)}" data-model="${escapeHtml(m.model_id)}">Edit</button>
        <button class="btn btn-ghost btn-sm btn-danger cp-model-remove" data-cp="${escapeHtml(p.id)}" data-model="${escapeHtml(m.model_id)}" data-model-row="${escapeHtml(m.id)}">Remove</button>
      </td>
    </tr>`;
  }).join("");
  const searchBar = p.models.length > MODEL_PAGE || needle
    ? `<div class="cp-models-tools">
        <input type="search" class="cp-model-search" data-cp-model-search="${escapeHtml(p.id)}" value="${escapeHtml(view.q)}" placeholder="Search ${p.models.length} registered models…" aria-label="Search registered models" autocomplete="off" spellcheck="false">
        <span class="muted small">${filtered.length} match${filtered.length === 1 ? "" : "es"}</span>
        <span class="pager-btns">
          <button type="button" class="btn btn-ghost btn-sm" data-cp-model-page="${escapeHtml(p.id)}" data-dir="-1" ${view.page <= 0 ? "disabled" : ""}>Previous</button>
          <span class="muted small">Page ${view.page + 1} / ${pages}</span>
          <button type="button" class="btn btn-ghost btn-sm" data-cp-model-page="${escapeHtml(p.id)}" data-dir="1" ${view.page >= pages - 1 ? "disabled" : ""}>Next</button>
        </span>
      </div>`
    : "";
  const pidAttr = escapeHtml(p.id);
  const counts = {};
  p.models.forEach((m) => { const st = _matchStatusOf(m); counts[st] = (counts[st] || 0) + 1; });
  const statusFilter = `<div class="cp-match-filter muted small" role="group" aria-label="Filter registered models by catalog match">Catalog match: ${_matchCounts(counts, { filterFor: p.id, active: view.status })}${view.status ? ` <button type="button" class="btn btn-ghost btn-sm" data-match-filter="" data-match-scope="${pidAttr}">Show all</button>` : ""}</div>`;
  const none = selected.size ? "" : "disabled";
  const bulk = `<div class="cp-model-bulk" role="toolbar" aria-label="${escapeHtml(t("providers.bulk_actions"))}">
      <label class="cp-bulk-select"><input type="checkbox" data-cp-check-all="${pidAttr}" data-cp-check-all-toolbar ${allFilteredSelected ? "checked" : ""}> <span>${escapeHtml(t("providers.select_all"))}</span></label>
      <span class="cp-bulk-count" aria-live="polite">${escapeHtml(tf("providers.selected_count", { count: selected.size }))}</span>
      <select class="cp-bulk-control" data-cp-bulk-cap data-cp="${pidAttr}" aria-label="${escapeHtml(t("providers.bulk_capability"))}">
        <option value="tools">${escapeHtml(t("providers.cap_tools"))}</option><option value="vision">${escapeHtml(t("providers.cap_vision"))}</option><option value="json_mode">${escapeHtml(t("providers.cap_json_mode"))}</option><option value="json_schema">${escapeHtml(t("providers.cap_json_schema"))}</option>
      </select>
      <select class="cp-bulk-control" data-cp-bulk-state data-cp="${pidAttr}" aria-label="${escapeHtml(t("providers.bulk_capability_state"))}">
        <option value="supported">${escapeHtml(t("providers.cap_supported"))}</option><option value="unsupported">${escapeHtml(t("providers.cap_unsupported"))}</option><option value="unknown">${escapeHtml(t("providers.cap_unknown"))}</option><option value="catalog">${escapeHtml(t("providers.cap_catalog"))}</option>
      </select>
      <button type="button" class="btn btn-ghost btn-sm" data-cp-bulk="restore_metadata" data-cp="${pidAttr}" ${none}>${escapeHtml(t("providers.apply"))}</button>
      <button type="button" class="btn btn-ghost btn-sm" data-cp-bulk="resolve_metadata" data-cp="${pidAttr}" ${none}>${escapeHtml(t("providers.resolve_metadata"))}</button>
      <button type="button" class="btn btn-ghost btn-sm" data-cp-bulk="enable" data-cp="${pidAttr}" ${none}>${escapeHtml(t("providers.enable"))}</button>
      <button type="button" class="btn btn-ghost btn-sm" data-cp-bulk="disable" data-cp="${pidAttr}" ${none}>${escapeHtml(t("providers.disable"))}</button>
      <button type="button" class="btn btn-ghost btn-sm btn-danger" data-cp-bulk="remove" data-cp="${pidAttr}" ${none}>${escapeHtml(t("providers.remove_selected"))}</button>
    </div>`;
  return `
    ${searchBar}
    ${statusFilter}
    ${bulk}
    <div class="table-wrap cp-models">
      <table>
        <thead><tr>
          <th scope="col" class="cp-col-check"><input type="checkbox" data-cp-check-all="${escapeHtml(p.id)}" ${allFilteredSelected ? "checked" : ""} aria-label="Select all filtered models"></th>
          <th scope="col">Model</th><th scope="col">Context</th><th scope="col">Tools</th><th scope="col">Vision</th><th scope="col">JSON mode</th><th scope="col">JSON schema</th><th scope="col">Reference in / out /1M</th><th scope="col">Custom in / out /1M</th><th scope="col">Availability</th><th scope="col"><span class="sr-only">Actions</span></th>
        </tr></thead>
        <tbody>${rows || '<tr><td colspan="11" class="muted small">No models match.</td></tr>'}</tbody>
      </table>
    </div>`;
}

/** Re-render only one provider's model table, leaving its search box (and
 *  the caret) alone. Full re-renders on every keystroke would fight the
 *  input the operator is typing into. */
function _rerenderModelsTable(pid) {
  const p = state.customProviders.find((x) => x.id === pid);
  const holder = $(`[data-cp-models-holder="${pid}"]`);
  if (!p || !holder) return;
  holder.innerHTML = _cpModelsTable(p);
  _bindModelTableEvents(holder, pid);
}

async function _refreshProviderRow(pid) {
  await loadCustomProviders();
  const p = state.customProviders.find((x) => x.id === pid);
  const rowEl = $(`.cp-row[data-cp-id="${pid}"]`);
  if (p && rowEl) {
    const holder = rowEl.querySelector(`[data-cp-models-holder="${pid}"]`);
    if (holder) {
      holder.innerHTML = _cpModelsTable(p);
      _bindModelTableEvents(holder, pid);
    }
    const modelCount = (p.models || []).length;
    const priced = (p.models || []).filter((m) => m.input_cost_per_token || m.output_cost_per_token).length;
    const readiness = {};
    (p.models || []).forEach((m) => { const st = _matchStatusOf(m); readiness[st] = (readiness[st] || 0) + 1; });
    const bits = _matchCounts(readiness);
    const line = rowEl.querySelector("[data-cp-readiness]");
    if (line) {
      line.innerHTML = `Catalog: ${bits || "—"}${priced < modelCount ? ` · ${modelCount - priced} without a confirmed price` : ""}`;
    } else if (modelCount) {
      const fresh = document.createElement("div");
      fresh.className = "cp-readiness muted small";
      fresh.setAttribute("data-cp-readiness", "");
      fresh.innerHTML = `Catalog: ${bits}${priced < modelCount ? ` · ${modelCount - priced} without a confirmed price` : ""}`;
      rowEl.querySelector(".cp-facts")?.after(fresh);
    }
    const countEl = rowEl.querySelector("[data-cp-model-count]");
    if (countEl) countEl.textContent = String(modelCount);
  } else {
    renderCustomProviders();
  }
}

function _editModel(pid, mid) {
  const p = state.customProviders.find((x) => x.id === pid);
  const m = p && (p.models || []).find((x) => x.model_id === mid);
  if (!m) return;
  const wrap = $(`[data-cp-add="${pid}"]`);
  if (!wrap) return;
  wrap.querySelector('[data-m="model_id"]').value = m.model_id;
  wrap.querySelector('[data-m="display_name"]').value = m.display_name || "";
  wrap.querySelector('[data-m="context_length"]').value = m.context_length || "";
  wrap.querySelector('[data-m="supports_tools"]').checked = !!m.supports_tools;
  wrap.querySelector('[data-m="supports_vision"]').checked = !!m.supports_vision;
  wrap.querySelector('[data-m="supports_json_mode"]').checked = !!m.supports_json_mode;
  wrap.querySelector('[data-m="supports_json_schema"]').checked = !!m.supports_json_schema;
  wrap.querySelector('[data-m="input_cost_per_million"]').value = m.input_cost_per_million != null ? m.input_cost_per_million : "";
  wrap.querySelector('[data-m="output_cost_per_million"]').value = m.output_cost_per_million != null ? m.output_cost_per_million : "";
  wrap.querySelector('[data-m="reference_input_cost_per_million"]').value = m.reference_input_cost_per_million != null ? m.reference_input_cost_per_million : "";
  wrap.querySelector('[data-m="reference_output_cost_per_million"]').value = m.reference_output_cost_per_million != null ? m.reference_output_cost_per_million : "";
  wrap.querySelector('[data-m="catalog_key"]').value = m.catalog_key || "";
  wrap.dataset.cpEdit = m.model_id;
  wrap.dataset.cpOriginal = JSON.stringify(Object.fromEntries(Array.from(wrap.querySelectorAll("[data-m]")).map((el) => [el.dataset.m, el.type === "checkbox" ? el.checked : el.value])));
  wrap.querySelector("[data-cp-addbtn]").textContent = "Update model";
  const hint = $(`[data-cp-edit-hint="${pid}"]`);
  if (hint) hint.textContent = `editing ${m.model_id}`;
}

const MI_STATE_CHIP = {
  configured: ["avail-auto", "Configured by you"],
  priced: ["avail-auto", "From catalog"],
  catalog_estimate: ["avail-pinned_only", "Catalog estimate"],
  cached: ["avail-unpriced", "Cached (stale)"],
  free: ["avail-pinned_only", "Free"],
  unknown: ["avail-not_deployable", "Unknown"],
};

function _cpDetailHtml(r) {
  const chip = MI_STATE_CHIP[r.price_state] || ["avail-not_deployable", r.price_state || "unknown"];
  const field = (label, f) => {
    const v = r.fields?.[f];
    if (!v || v.value == null) return "";
    const shown = f.endsWith("_per_million")
      ? `$${Number(v.value).toFixed(4)} / 1M`
      : f === "context" ? fmtNum(v.value) : (v.value ? "yes" : "no");
    return `<span><strong>${label}</strong> ${shown} <span class="muted small">via ${escapeHtml(v.source || "—")}${v.stale ? " (stale)" : ""}</span></span>`;
  };
  const srcs = (r.sources || r.per_source || []).map((s) => ({ ...s, found: s.found ?? s.has_entry }));
  const per = srcs.map((s) =>
    `<span class="cp-src ${s.found ? "on" : "off"}" title="${escapeHtml(s.last_error || s.source || "")}">${s.found ? "●" : "○"} ${escapeHtml(s.name)}${s.found && s.stale ? " (stale)" : ""}</span>`
  ).join(" ");
  return `
    <div class="explain-head ok"><span class="status-chip ${chip[0]}">${escapeHtml(chip[1])}</span> <code>${escapeHtml(r.model)}</code></div>
    <div class="cp-detail-facts">
      ${field("input", "input_per_million")}
      ${field("output", "output_per_million")}
      ${field("context", "context")}
      ${field("tools", "tools")}
      ${field("vision", "vision")}
      ${field("JSON mode", "json_mode")}
      ${field("JSON schema", "json_schema")}
    </div>
    <div class="cp-detail-facts">${per || '<span class="muted small">no sources enabled</span>'}</div>`;
}

async function _toggleCpModelDetails(pid, modelId, rowEl, btn) {
  const existing = rowEl.nextElementSibling;
  if (existing && existing.classList && existing.classList.contains("cp-detail-row")) {
    existing.remove();
    btn.setAttribute("aria-expanded", "false");
    btn.textContent = "Details";
    return;
  }
  btn.setAttribute("aria-expanded", "true");
  btn.textContent = "Hide";
  const tr = document.createElement("tr");
  tr.className = "cp-detail-row";
  tr.innerHTML = `<td colspan="11"><div class="cp-detail"><span class="muted small">Resolving…</span></div></td>`;
  rowEl.after(tr);
  const provider = state.customProviders.find((x) => x.id === pid);
  const modelKey = `${provider?.slug || ""}/${modelId}`;
  try {
    const r = await api(`/v1/model-intelligence/lookup?model=${encodeURIComponent(modelKey)}`);
    tr.querySelector(".cp-detail").innerHTML = _cpDetailHtml(r);
  } catch (e) {
    tr.querySelector(".cp-detail").innerHTML =
      `<span class="pill err">lookup failed</span> <span class="muted small">${escapeHtml(e.message)}</span>`;
  }
}

function _bindModelTableEvents(root, pid) {
  const provider = state.customProviders.find((x) => x.id === pid);
  const selected = _selection(pid);
  root.querySelectorAll(".cp-model-edit").forEach((b) =>
    b.addEventListener("click", () => _editModel(b.dataset.cp, b.dataset.model))
  );
  root.querySelectorAll(".cp-model-details").forEach((b) =>
    b.addEventListener("click", () => {
      const row = b.closest("tr");
      if (row) _toggleCpModelDetails(b.dataset.cp, b.dataset.model, row, b);
    })
  );
  root.querySelectorAll(".cp-model-remove").forEach((b) =>
    b.addEventListener("click", async () => {
      if (!confirm(tf("confirm.remove_model", {name: b.dataset.model}))) return;
      try {
        await api(`/v1/custom-providers/${b.dataset.cp}/models/${encodeURIComponent(b.dataset.model)}`, { method: "DELETE" });
        selected.delete(b.dataset.modelRow);
        await loadCustomProviders();
        renderCustomProviders();
      } catch (e) { toast(e.message, "err"); }
    })
  );

  root.querySelectorAll("[data-cp-check]").forEach((box) =>
    box.addEventListener("change", () => {
      if (box.checked) selected.add(box.dataset.cpCheck);
      else selected.delete(box.dataset.cpCheck);
      _rerenderModelsTable(pid);
    })
  );
  const boxes = root.querySelectorAll("[data-cp-check]");
  const checked = Array.from(boxes).filter((b) => b.checked).length;
  root.querySelectorAll("[data-cp-check-all]").forEach((all) => {
    all.indeterminate = checked > 0 && !all.checked;
    all.addEventListener("change", () => {
    const view = _modelView(pid);
    const needle = view.q.trim().toLowerCase();
    const filtered = needle
      ? provider.models.filter((m) => m.model_id.toLowerCase().includes(needle)
          || (m.display_name || "").toLowerCase().includes(needle))
      : provider.models;
    if (all.checked) filtered.forEach((m) => selected.add(m.id));
    else filtered.forEach((m) => selected.delete(m.id));
    _rerenderModelsTable(pid);
    });
  });

  root.querySelectorAll("[data-cp-cap]").forEach((sel) =>
    sel.addEventListener("change", async () => {
      try {
        await api(`/v1/custom-providers/${pid}/models/${encodeURIComponent(sel.dataset.modelRow)}`, {
          method: "PATCH",
          body: JSON.stringify({ capabilities: { [sel.dataset.cpCap]: sel.value } }),
        });
        await loadCustomProviders();
        _rerenderModelsTable(pid);
      } catch (e) { toast(e.message, "err"); }
    })
  );
  root.querySelectorAll("[data-cp-enable]").forEach((box) =>
    box.addEventListener("change", async () => {
      try {
        await api(`/v1/custom-providers/${pid}/models/${encodeURIComponent(box.dataset.cpEnable)}`, {
          method: "PATCH",
          body: JSON.stringify({ is_enabled: box.checked }),
        });
        await loadCustomProviders();
        _rerenderModelsTable(pid);
      } catch (e) { toast(e.message, "err"); }
    })
  );
  root.querySelectorAll("[data-cp-catalog]").forEach((host) => {
    const modelRowId = host.dataset.cpCatalog;
    const cands = (host.dataset.candidates || "").split("\n").map((k) => k.trim()).filter(Boolean);
    if (!host.gcSelect) {
      new GcSelect(host, {
        hostOptions: "cp-catalog-select",
        placeholderKey: "providers.catalog_key_ph",
        // An exact catalog key may be typed: the list shows the most likely
        // candidates (vendor first) but is capped. The server only accepts a
        // key that exists in an enabled source; otherwise the model stays
        // unmatched — nothing is guessed.
        allowCustom: true,
        customAccepts: _isFullCatalogKey,
        onChange: async (value) => {
          if (!value) return;
          try {
            await api(`/v1/custom-providers/${pid}/models/${encodeURIComponent(modelRowId)}`, {
              method: "PATCH",
              body: JSON.stringify({ catalog_key: value }),
            });
            await _refreshProviderRow(pid);
          } catch (e) { toast(e.message, "err"); }
        },
      });
    }
    host.gcSelect.setItems(cands);
    host.gcSelect.setValue("");
  });
  root.querySelectorAll("[data-cp-catalog-clear]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      try {
        await api(`/v1/custom-providers/${pid}/models/${encodeURIComponent(btn.dataset.cpCatalogClear)}`, {
          method: "PATCH",
          body: JSON.stringify({ clear_catalog_key: true }),
        });
        await _refreshProviderRow(pid);
      } catch (e) { toast(e.message, "err"); }
    })
  );
  root.querySelectorAll("[data-cp-bulk]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      if (!selected.size) return;
      const action = btn.dataset.cpBulk;
      const body = { action, model_ids: Array.from(selected) };
      if (action === "remove" && !confirm(tf("confirm.bulk_remove_models", { count: selected.size, plural: selected.size === 1 ? "" : "s" }))) return;
      if (action === "restore_metadata") {
        const cap = root.querySelector("[data-cp-bulk-cap]")?.value || "tools";
        const state = root.querySelector("[data-cp-bulk-state]")?.value || "unknown";
        body.capabilities = { [cap]: state };
      }
      btn.disabled = true;
      try {
        const result = await api(`/v1/custom-providers/${pid}/models/bulk`, { method: "POST", body: JSON.stringify(body) });
        if (action === "resolve_metadata") toast(tf("toast.metadata_resolved", result.summary), result.summary.failed ? "err" : "ok");
        if (action === "remove") selected.clear();
        await loadCustomProviders();
        renderCustomProviders();
      } catch (e) { toast(e.message, "err"); }
      finally { btn.disabled = false; }
    })
  );

  const search = root.querySelector("[data-cp-model-search]");
  if (search) {
    search.addEventListener("input", () => {
      const v = _modelView(pid);
      v.q = search.value;
      v.page = 0;
      _rerenderModelsTable(pid);
      const again = $(`[data-cp-models-holder="${pid}"] [data-cp-model-search]`);
      if (again) { again.focus(); again.setSelectionRange(again.value.length, again.value.length); }
    });
  }
  root.querySelectorAll("[data-cp-model-page]").forEach((b) =>
    b.addEventListener("click", () => {
      const v = _modelView(pid);
      v.page = Math.max(0, v.page + parseInt(b.dataset.dir, 10));
      _rerenderModelsTable(pid);
    })
  );
}

// Per-provider fetch state, keyed by provider id.
const FETCH_STATE = {};
// Per-provider "Manage Models" panel open/closed, survives re-renders.
const MANAGE_OPEN = {};

function _fmtFetchedAt(iso) {
  if (!iso) return "never";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const diff = Date.now() - d.getTime();
    if (diff < 60000) return "just now";
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

// Resolution status of a discovered model against the Model Intelligence
// catalog. Always shown before registration so the operator knows which ids
// will inherit context/capabilities/reference pricing and which need a manual
// catalog pick.
function _fetchResolvedMeta(m, fs) {
  const p = m.preview || null;
  if (!p) return "";
  const total = p.candidate_total || (p.candidates || []).length;
  const detail = p.catalog_key
    ? `Key: ${p.catalog_key}.`
    : p.status === "ambiguous" ? `${total} catalog entries share this id; pick one below or leave it unmatched.` : "";
    const chosen = (fs.keys || {})[m.id] || "";
  let picker = "";
  if (p.status === "ambiguous" || (!p.catalog_key && (p.candidates || []).length)) {
    picker = `<div class="cp-fetch-key" data-fetch-key="${escapeHtml(m.id)}" data-candidates="${escapeHtml((p.candidates || []).join("\n"))}" data-chosen="${escapeHtml(chosen || "")}" aria-label="Catalog key for ${escapeHtml(m.id)}"></div>`;
  }
  return `${_matchBadge(p.status, detail)}${picker}`;
}

function _fetchListItems(pid) {
  const fs = FETCH_STATE[pid];
  if (!fs) return "";
  const models = fs.models || [];
  const filter = (fs.filter || "").toLowerCase();
  const statusFilter = fs.status || "";
  const filtered = models.filter((m) =>
    (!filter || m.id.toLowerCase().includes(filter))
    && (!statusFilter || (m.preview && m.preview.status) === statusFilter));
  const registered = fs.registered || new Set();
  const selected = fs.selected || new Set();
  // Rendering thousands of checkboxes freezes the page; show a window and
  // let search narrow it. "Select All" still applies to every match.
  const FETCH_RENDER_CAP = 200;
  const shown = filtered.slice(0, FETCH_RENDER_CAP);
  const more = filtered.length - shown.length;
  const listItems = shown.map((m) => {
    const isReg = registered.has(m.id);
    const isSel = selected.has(m.id);
    const checked = isReg || isSel ? "checked" : "";
    const disabled = isReg ? "disabled" : "";
    const badge = isReg ? ' <span class="pill ok" title="Already registered on this provider">registered</span>' : "";
    // Provider-reported limits are evidence about this deployment; show them
    // so the operator sees what registration will store. Absent = unknown.
    const limits = [
      m.context_window ? `${fmtNum(m.context_window)} ctx` : "",
      m.max_output_tokens ? `${fmtNum(m.max_output_tokens)} out` : "",
    ].filter(Boolean).join(" · ");
    const meta = limits
      ? ` · <span class="muted" title="Reported by the provider's /models endpoint">${escapeHtml(limits)}</span>`
      : (m.owned_by ? ` · <span class="muted">${escapeHtml(m.owned_by)}</span>` : "");
    return `<div class="cp-fetch-item ${isReg ? "reg" : ""}">
      <label class="cp-fetch-main">
        <input type="checkbox" data-fetch-check="${escapeHtml(m.id)}" ${checked} ${disabled}>
        <code>${escapeHtml(m.id)}</code>${badge}${meta}
      </label>
      ${isReg ? "" : _fetchResolvedMeta(m, fs)}
    </div>`;
  }).join("");
  const tail = more > 0
    ? `<span class="muted small cp-fetch-more">Showing ${shown.length} of ${filtered.length}. Search to narrow the list.</span>`
    : "";
  return (listItems + tail) || '<span class="muted small">No models match your search.</span>';
}

function renderFetchList(pid) {
  const panel = $(`[data-cp-fetch-panel="${pid}"]`);
  if (!panel) return;
  const listEl = panel.querySelector(".cp-fetch-list");
  if (listEl) listEl.innerHTML = _fetchListItems(pid);
}

function renderFetchPanel(pid) {
  const panel = $(`[data-cp-fetch-panel="${pid}"]`);
  if (!panel) return;
  const fs = FETCH_STATE[pid];
  if (!fs) { panel.hidden = true; return; }
  panel.hidden = false;
  if (fs.error) {
    panel.innerHTML = `<div class="cp-test-result err">${escapeHtml(fs.error)}</div>`;
    return;
  }
  const models = fs.models || [];
  const summary = fs.summary || {};
  const regCount = models.filter((m) => (fs.registered || new Set()).has(m.id)).length;
  const summaryPills = _matchCounts(summary, { filterFor: `fetch:${pid}`, active: fs.status || "" });
  panel.innerHTML = `
    <div class="cp-fetch-head">
      <input data-fetch-search type="text" placeholder="Search models…" value="${escapeHtml(fs.filter || "")}" autocomplete="off" spellcheck="false">
      <span class="muted small">${models.length} model${models.length === 1 ? "" : "s"} · fetched ${_fmtFetchedAt(fs.fetchedAt)}</span>
    </div>
    ${summaryPills ? `<div class="muted small cp-fetch-summary" data-fetch-summary role="group" aria-label="Filter discovered models by catalog match">Catalog match: ${summaryPills}${fs.status ? ` <button type="button" class="btn btn-ghost btn-sm" data-match-filter="" data-match-scope="fetch:${escapeHtml(pid)}">Show all</button>` : ""} · ${regCount} registered
      <details class="policy-help cp-match-help"><summary>What do these mean?</summary>
        <p><strong>Resolved</strong>: exactly one catalog entry has this id, so context, capabilities and reference prices are inherited. <strong>Ambiguous</strong>: several catalog entries (often resellers) share the id; nothing is inherited until you pick the key that really is this model. <strong>Unmatched</strong>: no catalog entry exists (custom, renamed, abliterated or uncensored variants); capabilities and prices stay Unknown until you set them. Auto only routes a model with a confirmed price.</p>
      </details></div>` : ""}
    <div class="cp-fetch-list">${_fetchListItems(pid)}</div>
    <div class="cp-fetch-actions">
      <button class="btn btn-ghost btn-sm" data-fetch-selectall>Select All</button>
      <button class="btn btn-ghost btn-sm" data-fetch-clear>Clear Selection</button>
      <button class="btn btn-ghost btn-sm" data-fetch-refresh>Refresh</button>
      <button class="btn btn-primary btn-sm" data-fetch-add>Add Selected Models</button>
    </div>`;
}

function renderCustomProviders() {
  const card = $("#custom-providers-card");
  const list = $("#custom-providers-list");
  if (!card || !list) return;
  if (!state.customProviders.length) {
    card.hidden = true;
    return;
  }
  card.hidden = false;
  list.innerHTML = state.customProviders.map((p) => {
    const modelCount = (p.models || []).length;
    const manageOpen = !!MANAGE_OPEN[p.id];
    const priced = (p.models || []).filter((m) => m.input_cost_per_token || m.output_cost_per_token).length;
    const healthy = p.decryptable !== false && p.is_enabled;
    const readiness = {};
    (p.models || []).forEach((m) => { const st = _matchStatusOf(m); readiness[st] = (readiness[st] || 0) + 1; });
    const readinessBits = _matchCounts(readiness);
    const readinessLine = modelCount
      ? `<div class="cp-readiness muted small" data-cp-readiness>Catalog: ${readinessBits || "—"}${priced < modelCount ? ` · ${modelCount - priced} without a confirmed price` : ""}</div>`
      : "";
    return `
    <div class="cp-row ${p.is_enabled ? "" : "is-off"}" data-cp-id="${escapeHtml(p.id)}">
      <div class="cp-card-head">
        <span class="cp-mark ${healthy ? "on" : "off"}" aria-hidden="true">${escapeHtml((p.display_name || "?").trim().charAt(0).toUpperCase())}</span>
        <div class="cp-identity">
          <div class="cp-row-head">
            <span class="name" data-cp-name>${escapeHtml(p.display_name)}</span>
            <span class="proto-badge" title="GeekCubo talks to this provider with the OpenAI-compatible chat/completions API">OpenAI-compatible</span>
            ${_cpStatusPill(p)}
            ${_cpAutoPill(p)}
          </div>
          <div class="cp-endpoint">
            <code class="cp-slug">${escapeHtml(p.slug)}/&lt;model&gt;</code>
            <span class="cp-dot" aria-hidden="true">·</span>
            <span class="cp-url" data-cp-url title="${escapeHtml(p.base_url)}">${escapeHtml(p.base_url)}</span>
          </div>
        </div>
        <div class="cp-head-actions">
          <button class="btn btn-ghost btn-sm" data-cp-edit="${escapeHtml(p.id)}">Edit</button>
          <details class="cp-menu">
            <summary class="btn btn-ghost btn-sm" aria-label="More actions for ${escapeHtml(p.display_name)}">More</summary>
            <div class="cp-menu-items">
              <button type="button" class="cp-menu-item" data-cp-test="${escapeHtml(p.id)}">Test connection</button>
              <button type="button" class="cp-menu-item" data-cp-fetch="${escapeHtml(p.id)}">Fetch available models</button>
              <button type="button" class="cp-menu-item" data-cp-toggle="${escapeHtml(p.id)}">${p.is_enabled ? "Disable provider" : "Enable provider"}</button>
              <button type="button" class="cp-menu-item" data-cp-auto="${escapeHtml(p.id)}">${p.eligible_for_auto ? "Exclude from Auto" : "Include in Auto"}</button>
              <button type="button" class="cp-menu-item danger" data-cp-remove="${escapeHtml(p.id)}">Remove provider</button>
            </div>
          </details>
        </div>
      </div>

      <dl class="cp-facts">
        <div class="cp-fact">
          <dt>Models</dt>
          <dd><span data-cp-model-count>${modelCount}</span>${priced < modelCount ? ` <span class="cp-warn" title="Models without a configured price are skipped by Auto — it never assumes they are free">${modelCount - priced} unpriced</span>` : ""}</dd>
        </div>
        <div class="cp-fact">
          <dt>Auto</dt>
          <dd>${p.eligible_for_auto ? "Eligible" : "Excluded"}</dd>
        </div>
        <div class="cp-fact">
          <dt>Key</dt>
          <dd><code data-cp-key>${escapeHtml(p.key_prefix || "—")}</code></dd>
        </div>
        <div class="cp-fact">
          <dt>Last synced</dt>
          <dd>${escapeHtml(_fmtFetchedAt(p.last_models_fetched_at))}</dd>
        </div>
      </dl>
      ${readinessLine}
      <p class="cp-meta cp-summary sr-only">Base URL: <code>${escapeHtml(p.base_url)}</code> · Key: <code>${escapeHtml(p.key_prefix || "—")}</code> · Models fetched: <strong>${_fmtFetchedAt(p.last_models_fetched_at)}</strong></p>

      <div class="cp-actions">
        <button class="btn btn-ghost btn-sm" data-cp-manage="${escapeHtml(p.id)}" aria-expanded="${manageOpen}">${manageOpen ? "Hide models" : `Manage models (${modelCount})`}</button>
      </div>
      <form class="cp-edit inline-form" data-cp-edit-form="${escapeHtml(p.id)}" hidden novalidate>
        <label class="field flex-grow"><span class="field-label">Provider name</span>
          <input data-e="display_name" value="${escapeHtml(p.display_name)}" autocomplete="off" spellcheck="false"></label>
        <label class="field flex-grow"><span class="field-label">API base URL</span>
          <input data-e="base_url" value="${escapeHtml(p.base_url)}" autocomplete="off" spellcheck="false"></label>
        <label class="field flex-grow"><span class="field-label">API key</span>
          <input data-e="api_key" type="password" placeholder="Leave blank to keep the current key" autocomplete="new-password" spellcheck="false"></label>
        <button type="submit" class="btn btn-primary btn-sm">Save changes</button>
        <button type="button" class="btn btn-ghost btn-sm" data-cp-edit-cancel="${escapeHtml(p.id)}">Cancel</button>
        <p class="field-help custom-form-error" data-cp-edit-error="${escapeHtml(p.id)}" role="alert" hidden></p>
      </form>
      <div class="cp-test-result" data-cp-result="${escapeHtml(p.id)}"></div>
      <div class="cp-fetch-panel" data-cp-fetch-panel="${escapeHtml(p.id)}" hidden></div>
      <div class="cp-manage" data-cp-manage-panel="${escapeHtml(p.id)}" ${manageOpen ? "" : "hidden"}>
      <div data-cp-models-holder="${escapeHtml(p.id)}">${_cpModelsTable(p)}</div>
      <div class="model-add" data-cp-add="${escapeHtml(p.id)}">
        <label class="field"><span class="field-label">Model ID</span><input data-m="model_id" placeholder="gpt-4o" autocomplete="off" spellcheck="false"></label>
        <label class="field"><span class="field-label">Display name</span><input data-m="display_name" placeholder="GPT-4o" autocomplete="off" spellcheck="false"></label>
        <label class="field"><span class="field-label">Context limit</span><input data-m="context_length" type="number" min="0" placeholder="128000"></label>
        <label class="checkline"><input data-m="supports_tools" type="checkbox">Tools</label>
        <label class="checkline"><input data-m="supports_vision" type="checkbox">Vision</label>
        <label class="checkline"><input data-m="supports_json_mode" type="checkbox">JSON mode</label>
        <label class="checkline"><input data-m="supports_json_schema" type="checkbox">JSON schema</label>
        <label class="field"><span class="field-label">Custom $ in /1M</span><input data-m="input_cost_per_million" type="number" min="0" step="0.001" placeholder="2.50"></label>
        <label class="field"><span class="field-label">Custom $ out /1M</span><input data-m="output_cost_per_million" type="number" min="0" step="0.001" placeholder="10.00"></label>
        <label class="field"><span class="field-label">Reference $ in /1M <span class="muted">(optional estimate)</span></span><input data-m="reference_input_cost_per_million" type="number" min="0" step="0.001" placeholder="auto from catalog"></label>
        <label class="field"><span class="field-label">Reference $ out /1M <span class="muted">(optional estimate)</span></span><input data-m="reference_output_cost_per_million" type="number" min="0" step="0.001" placeholder="auto from catalog"></label>
        <label class="field"><span class="field-label">Catalog key <span class="muted">(optional override)</span></span><input data-m="catalog_key" placeholder="openai/gpt-4o" autocomplete="off" spellcheck="false"></label>
        <button class="btn btn-primary btn-sm" data-cp-addbtn="${escapeHtml(p.id)}">Add model</button>
        <span class="muted small" data-cp-edit-hint="${escapeHtml(p.id)}"></span>
      </div>
      </div>
    </div>`;
  }).join("");

  state.customProviders.forEach((p) => {
    renderFetchPanel(p.id);
    if (FETCH_STATE[p.id]) bindFetchPanel(p.id);
  });

  // A native <details> stays open after a menu item runs, and clicking
  // elsewhere never closes it. Close on outside click / Escape instead.
  document.addEventListener("click", (e) => {
    $$(".cp-menu[open]").forEach((d) => {
      if (!d.contains(e.target)) d.removeAttribute("open");
    });
  });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    $$(".cp-menu[open]").forEach((d) => d.removeAttribute("open"));
  });
  $$("[data-cp-manage]").forEach((b) =>
    b.addEventListener("click", () => {
      const pid = b.dataset.cpManage;
      MANAGE_OPEN[pid] = !MANAGE_OPEN[pid];
      const panel = $(`[data-cp-manage-panel="${pid}"]`);
      if (panel) panel.hidden = !MANAGE_OPEN[pid];
      b.textContent = MANAGE_OPEN[pid] ? "Hide Models" : "Manage Models";
      b.setAttribute("aria-expanded", String(!!MANAGE_OPEN[pid]));
    })
  );
  $$("[data-cp-edit]").forEach((b) =>
    b.addEventListener("click", () => {
      const pid = b.dataset.cpEdit;
      const form = $(`[data-cp-edit-form="${pid}"]`);
      if (!form) return;
      form.hidden = !form.hidden;
      if (!form.hidden) form.querySelector('[data-e="display_name"]').focus();
    })
  );
  $$("[data-cp-edit-cancel]").forEach((b) =>
    b.addEventListener("click", () => {
      const form = $(`[data-cp-edit-form="${b.dataset.cpEditCancel}"]`);
      if (form) form.hidden = true;
    })
  );
  $$("[data-cp-edit-form]").forEach((form) =>
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const pid = form.dataset.cpEditForm;
      const p = state.customProviders.find((x) => x.id === pid);
      if (!p) return;
      const errEl = $(`[data-cp-edit-error="${pid}"]`);
      const setErr = (msg) => { if (errEl) { errEl.hidden = !msg; errEl.textContent = msg || ""; } };
      const name = form.querySelector('[data-e="display_name"]').value.trim();
      const baseUrl = form.querySelector('[data-e="base_url"]').value.trim();
      const apiKey = form.querySelector('[data-e="api_key"]').value.trim();
      // Validate name/URL like creation; the key is optional on edit.
      const problem = validateCustomProviderInput({ name, baseUrl, apiKey: apiKey || "unchanged" });
      if (problem) { setErr(problem); return; }
      // Send only fields that changed, so each one can be edited independently
      // (and an untouched URL isn't re-resolved by the SSRF guard).
      const patch = {};
      if (name !== p.display_name) patch.display_name = name;
      if (baseUrl !== p.base_url) patch.base_url = baseUrl;
      if (apiKey) patch.api_key = apiKey;
      if (!Object.keys(patch).length) { setErr("Nothing changed."); return; }
      try {
        await api(`/v1/custom-providers/${pid}`, { method: "PUT", body: JSON.stringify(patch) });
        setErr("");
        toast(tf("toast.updated", {name}), "ok");
        await loadCustomProviders();
        renderCustomProviders();
      } catch (err) {
        setErr(err.message);
        toast(err.message, "err");
      }
    })
  );

  $$("[data-cp-models-holder]").forEach((holder) =>
    _bindModelTableEvents(holder, holder.dataset.cpModelsHolder)
  );
  $$("[data-cp-addbtn]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const pid = btn.dataset.cpAddbtn;
      const wrap = $(`[data-cp-add="${pid}"]`);
      const g = (k) => wrap.querySelector(`[data-m="${k}"]`);
      const modelId = g("model_id").value.trim();
      if (!modelId) { toast(t("toast.model_id_empty"), "err"); return; }
      const existing = state.customProviders.find((p) => p.id === pid);
      const editId = wrap.dataset.cpEdit;
      const inputM = g("input_cost_per_million").value;
      const outputM = g("output_cost_per_million").value;
      const refInputM = g("reference_input_cost_per_million").value;
      const refOutputM = g("reference_output_cost_per_million").value;
      const entry = {
        model_id: modelId,
        display_name: g("display_name").value.trim() || modelId,
        context_length: g("context_length").value ? parseInt(g("context_length").value, 10) : null,
        supports_tools: g("supports_tools").checked,
        supports_vision: g("supports_vision").checked,
        supports_json_mode: g("supports_json_mode").checked,
        supports_json_schema: g("supports_json_schema").checked,
        input_cost_per_million: inputM ? parseFloat(inputM) : null,
        output_cost_per_million: outputM ? parseFloat(outputM) : null,
        reference_input_cost_per_million: refInputM ? parseFloat(refInputM) : null,
        reference_output_cost_per_million: refOutputM ? parseFloat(refOutputM) : null,
        catalog_key: g("catalog_key").value.trim() || null,
      };
      let body = entry;
      let url = `/v1/custom-providers/${pid}/models`;
      let method = "POST";
      if (editId) {
        const original = JSON.parse(wrap.dataset.cpOriginal);
        body = {};
        const capabilities = {};
        for (const el of wrap.querySelectorAll("[data-m]")) {
          const key = el.dataset.m;
          const value = el.type === "checkbox" ? el.checked : el.value;
          if (value === original[key]) continue;
          if (key.startsWith("supports_")) {
            capabilities[key === "supports_json_mode" ? "json_mode" : key.slice(9)] = value ? "supported" : "unsupported";
          } else if (key === "catalog_key") {
            if (value.trim()) body.catalog_key = value.trim();
            else body.clear_catalog_key = true;
          } else if (key === "context_length") {
            if (value) body.context_length = Number(value);
            else body.clear_context = true;
          } else if (key.includes("cost_per_million")) {
            const reference = key.startsWith("reference_");
            const prefix = reference ? "reference_" : "";
            const inKey = `${prefix}input_cost_per_million`;
            const outKey = `${prefix}output_cost_per_million`;
            if (!g(inKey).value && !g(outKey).value) {
              body[reference ? "clear_reference_price" : "clear_custom_price"] = true;
            } else {
              body[reference ? key : `custom_${key}`] = Number(value || 0);
            }
          } else {
            body[key] = value.trim();
          }
        }
        if (Object.keys(capabilities).length) body.capabilities = capabilities;
        const model = existing.models.find((m) => m.model_id === editId);
        url += `/${encodeURIComponent(model.id)}`;
        method = "PATCH";
      } else {
        if (existing.models.some((m) => m.model_id === modelId)) {
          toast(t("toast.model_id_dup"), "err");
          return;
        }
        body = [entry];
      }
      try {
        await api(url, { method, body: JSON.stringify(body) });
        wrap.dataset.cpEdit = "";
        btn.textContent = "Add model";
        const hint = $(`[data-cp-edit-hint="${pid}"]`);
        if (hint) hint.textContent = "";
        wrap.querySelector('[data-m="model_id"]').value = "";
        wrap.querySelector('[data-m="display_name"]').value = "";
        wrap.querySelector('[data-m="context_length"]').value = "";
        wrap.querySelector('[data-m="supports_tools"]').checked = false;
        wrap.querySelector('[data-m="supports_vision"]').checked = false;
        wrap.querySelector('[data-m="supports_json_mode"]').checked = false;
        wrap.querySelector('[data-m="supports_json_schema"]').checked = false;
        wrap.querySelector('[data-m="input_cost_per_million"]').value = "";
        wrap.querySelector('[data-m="output_cost_per_million"]').value = "";
        wrap.querySelector('[data-m="reference_input_cost_per_million"]').value = "";
        wrap.querySelector('[data-m="reference_output_cost_per_million"]').value = "";
        wrap.querySelector('[data-m="catalog_key"]').value = "";
        await loadCustomProviders();
        renderCustomProviders();
        toast(t("toast.model_saved"), "ok");
      } catch (e) { toast(e.message, "err"); }
    })
  );
  $$("[data-cp-fetch]").forEach((b) =>
    b.addEventListener("click", async () => {
      const pid = b.dataset.cpFetch;
      await doFetchModels(pid, true);
    })
  );
  $$("[data-cp-test]").forEach((b) =>
    b.addEventListener("click", async () => {
      const pid = b.dataset.cpTest;
      const resultEl = $(`[data-cp-result="${pid}"]`);
      resultEl.textContent = "Testing…";
      resultEl.className = "cp-test-result";
      try {
        const r = await api(`/v1/custom-providers/${pid}/test`, { method: "POST", body: JSON.stringify({}) });
        if (r.ok) {
          const modelStr = r.resolved_model
            ? `Resolved model: ${r.resolved_model}`
            : (r.models && r.models.length ? `Upstream models: ${r.models.slice(0, 12).join(", ")}` : "Connected");
          resultEl.textContent = `OK — ${modelStr}`;
          resultEl.className = "cp-test-result ok";
        } else {
          resultEl.textContent = `Failed (${r.error_type || "unknown"}): ${r.error}`;
          resultEl.className = "cp-test-result err";
        }
      } catch (e) {
        resultEl.textContent = `Failed: ${e.message}`;
        resultEl.className = "cp-test-result err";
      }
    })
  );
  $$("[data-cp-toggle]").forEach((b) =>
    b.addEventListener("click", async () => {
      const pid = b.dataset.cpToggle;
      const p = state.customProviders.find((x) => x.id === pid);
      try {
        await api(`/v1/custom-providers/${pid}`, { method: "PUT", body: JSON.stringify({ is_enabled: !p.is_enabled }) });
        await loadCustomProviders();
        renderCustomProviders();
      } catch (e) { toast(e.message, "err"); }
    })
  );
  $$("[data-cp-auto]").forEach((b) =>
    b.addEventListener("click", async () => {
      const pid = b.dataset.cpAuto;
      const p = state.customProviders.find((x) => x.id === pid);
      try {
        await api(`/v1/custom-providers/${pid}`, { method: "PUT", body: JSON.stringify({ eligible_for_auto: !p.eligible_for_auto }) });
        await loadCustomProviders();
        renderCustomProviders();
      } catch (e) { toast(e.message, "err"); }
    })
  );
  $$("[data-cp-remove]").forEach((b) =>
    b.addEventListener("click", async () => {
      const pid = b.dataset.cpRemove;
      const p = state.customProviders.find((x) => x.id === pid);
      if (!confirm(tf("confirm.remove_custom", {name: p.display_name}))) return;
      try {
        await api(`/v1/custom-providers/${pid}`, { method: "DELETE" });
        delete FETCH_STATE[pid];
        await loadCustomProviders();
        renderCustomProviders();
        renderOverview();
        syncOnboarding();
      } catch (e) { toast(e.message, "err"); }
    })
  );
}

async function doFetchModels(pid, force) {
  const panel = $(`[data-cp-fetch-panel="${pid}"]`);
  if (panel) { panel.hidden = false; panel.innerHTML = '<span class="muted small">Fetching available models…</span>'; }
  try {
    const r = await api(`/v1/custom-providers/${pid}/fetch-models`, {
      method: "POST",
      body: JSON.stringify({ force: !!force }),
    });
    const prev = FETCH_STATE[pid];
    const prevSelected = prev ? prev.selected : new Set();
    const prevKeys = prev ? (prev.keys || {}) : {};
    if (r.ok) {
      const ids = new Set((r.models || []).map((m) => m.id));
      FETCH_STATE[pid] = {
        models: r.models || [],
        summary: r.preview_summary || null,
        registered: new Set(r.registered_model_ids || []),
        selected: new Set([...prevSelected].filter((id) => ids.has(id))),
        keys: Object.fromEntries(Object.entries(prevKeys).filter(([id]) => ids.has(id))),
        fetchedAt: r.fetched_at,
        error: null,
        filter: "",
      };
    } else {
      FETCH_STATE[pid] = {
        models: [],
        summary: null,
        registered: new Set(),
        selected: new Set(),
        keys: {},
        fetchedAt: null,
        error: `Failed (${r.error_type || "unknown"}): ${r.error}`,
        filter: "",
      };
    }
    await loadCustomProviders();
    // renderCustomProviders() re-renders and re-binds every fetch panel that
    // has FETCH_STATE — binding again here would attach duplicate handlers.
    renderCustomProviders();
  } catch (e) {
    FETCH_STATE[pid] = { models: [], summary: null, registered: new Set(), selected: new Set(), keys: {}, fetchedAt: null, error: `Failed: ${e.message}`, filter: "" };
    renderCustomProviders();
  }
}

function bindFetchPanel(pid) {
  const panel = $(`[data-cp-fetch-panel="${pid}"]`);
  if (!panel) return;
  const fs = () => FETCH_STATE[pid];
  const search = panel.querySelector("[data-fetch-search]");
  if (search) {
    search.addEventListener("input", () => {
      fs().filter = search.value;
      renderFetchList(pid);
      bindFetchCheckboxes(pid);
      bindFetchKeyPickers(pid);
    });
  }
  const selectAll = panel.querySelector("[data-fetch-selectall]");
  if (selectAll) {
    selectAll.addEventListener("click", () => {
      const s = fs();
      (s.models || []).forEach((m) => { if (!s.registered.has(m.id)) s.selected.add(m.id); });
      renderFetchList(pid);
      bindFetchCheckboxes(pid);
      bindFetchKeyPickers(pid);
    });
  }
  const clear = panel.querySelector("[data-fetch-clear]");
  if (clear) {
    clear.addEventListener("click", () => {
      fs().selected = new Set();
      renderFetchList(pid);
      bindFetchCheckboxes(pid);
      bindFetchKeyPickers(pid);
    });
  }
  const refresh = panel.querySelector("[data-fetch-refresh]");
  if (refresh) {
    refresh.addEventListener("click", async () => { await doFetchModels(pid, true); });
  }
  const addBtn = panel.querySelector("[data-fetch-add]");
  if (addBtn) {
    addBtn.addEventListener("click", async () => {
      const s = fs();
      const toAdd = [...s.selected].filter((id) => !s.registered.has(id));
      if (!toAdd.length) { toast(t("toast.select_one_model"), "err"); return; }
      const body = toAdd.map((id) => {
        const entry = { model_id: id, display_name: id };
        const key = (s.keys || {})[id];
        if (key) entry.catalog_key = key;
        return entry;
      });
      try {
        await api(`/v1/custom-providers/${pid}/models`, { method: "POST", body: JSON.stringify(body) });
        const s = fs();
        toAdd.forEach((id) => { s.registered.add(id); s.selected.delete(id); delete (s.keys || {})[id]; });
        toast(toAdd.length === 1 ? t("toast.added_models_one") : tf("toast.added_models_many", {count: toAdd.length}), "ok");
        MANAGE_OPEN[pid] = true;
        await loadCustomProviders();
        renderCustomProviders();
      } catch (e) { toast(e.message, "err"); }
    });
  }
  bindFetchCheckboxes(pid);
  bindFetchKeyPickers(pid);
}

function bindFetchCheckboxes(pid) {
  const panel = $(`[data-cp-fetch-panel="${pid}"]`);
  if (!panel) return;
  const s = () => FETCH_STATE[pid];
  panel.querySelectorAll("[data-fetch-check]").forEach((cb) => {
    cb.addEventListener("change", () => {
      const id = cb.dataset.fetchCheck;
      if (cb.checked) s().selected.add(id); else s().selected.delete(id);
    });
  });
}

function bindFetchKeyPickers(pid) {
  const panel = $(`[data-cp-fetch-panel="${pid}"]`);
  if (!panel) return;
  panel.querySelectorAll("[data-fetch-key]").forEach((host) => {
    const modelId = host.dataset.fetchKey;
    const cands = (host.dataset.candidates || "").split("\n").map((k) => k.trim()).filter(Boolean);
    if (!host.gcSelect) {
      new GcSelect(host, {
        hostOptions: "cp-fetch-key",
        placeholderKey: "providers.catalog_key_ph",
        // An exact catalog key may be typed: the list shows the most likely
        // candidates (vendor first) but is capped. The server only accepts a
        // key that exists in an enabled source; otherwise the model stays
        // unmatched — nothing is guessed.
        allowCustom: true,
        customAccepts: _isFullCatalogKey,
        onChange: (value) => {
          const fs = FETCH_STATE[pid];
          if (!fs) return;
          if (!fs.keys) fs.keys = {};
          if (value) fs.keys[modelId] = value;
          else delete fs.keys[modelId];
        },
      });
    }
    host.gcSelect.setItems(cands);
    host.gcSelect.setValue(host.dataset.chosen || (FETCH_STATE[pid]?.keys || {})[modelId] || "");
  });
}

/* ==========================================================================
   ROUTING
   ========================================================================== */
async function loadRouting() {
  try {
    const r = await api("/v1/routing");
    state.routing = r;
  } catch (e) {
    toast(tf("toast.load_routing_failed", {msg: e.message}), "err");
  }
}

function renderRouting() {
  $$(".strategy-card").forEach((c) => {
    const selected = c.dataset.value === state.routing.strategy;
    c.classList.toggle("selected", selected);
    const input = c.querySelector("input");
    if (input) {
      input.checked = selected;
      input.setAttribute("aria-checked", String(selected));
    }
  });
  const warn = $("#routing-warnings");
  if (warn) {
    const list = state.routing.warnings || [];
    warn.hidden = !list.length;
    warn.innerHTML = list.map((w) => `<li>${escapeHtml(w)}</li>`).join("");
  }
  renderPolicyForm();
  renderPoolChips();
}

function bindRouting() {
  $$(".strategy-card").forEach((c) => {
    c.addEventListener("click", async (e) => {
      e.preventDefault();
      const val = c.dataset.value;
      if (val === state.routing.strategy) return;
      const prev = state.routing.strategy;
      state.routing.strategy = val;
      renderRouting();
      try {
        state.routing = await api("/v1/routing", { method: "PUT", body: JSON.stringify({ strategy: val }) });
        renderRouting();
        toast(tf("toast.routing_strategy", {name: c.querySelector(".strategy-title")?.textContent || val}), "ok");
        try {
          await loadQualityPreview();
          renderQualityPreview();
        } catch (_) { /* preview is non-critical, never block strategy change */ }
        syncOnboarding();
      } catch (err) {
        state.routing.strategy = prev;
        renderRouting();
        toast(err.message, "err");
      }
    });
  });
  bindPoolPicker();
  bindPolicyForm();
  bindExplain();
}

/* ─── routing policy ─── */
function currentPolicy() {
  return state.routing.policy || {
    pools: { mundane: [], hard: [], fallback: [] },
    fallback: { enabled: true, max_attempts: 5, models: [] },
    gated: {}, escalation: { mode: "off" }, stickiness: { enabled: false, ttl_minutes: 30 },
    balanced_min_quality: 0,
  };
}

function renderPolicyForm() {
  if (!$("#routing-policy-form")) return;
  // Routing data can arrive more than once on page load (boot loader + tab
  // loader). Re-filling the form then would silently discard what the
  // operator has typed since; keep their edits until they save.
  if ($("#routing-policy-form").dataset.dirty === "1") return;
  const p = currentPolicy();
  const g = p.gated || {}, e = p.escalation || {}, f = p.fallback || {}, st = p.stickiness || {};
  $("#pol-fallback-enabled").checked = f.enabled !== false;
  $("#pol-fallback-max").value = f.max_attempts ?? 5;
  $("#pol-min-quality").value = p.balanced_min_quality ?? 0;
  $("#pol-gated-tools").checked = g.hard_on_tools !== false;
  $("#pol-gated-vision").checked = g.hard_on_vision !== false;
  $("#pol-gated-messages").value = g.hard_on_min_messages ?? 8;
  $("#pol-gated-chars").value = g.hard_on_min_prompt_chars ?? 6000;
  $("#pol-gated-mundane-fallback").checked = g.allow_mundane_fallback !== false;
  $("#pol-esc-mode").value = e.mode || "off";
  $("#pol-esc-threshold").value = e.failure_threshold ?? 2;
  $("#pol-esc-max").value = e.max_per_conversation ?? 2;
  $("#pol-esc-to").value = e.to_pool || "hard";
  $("#pol-esc-shadow").checked = !!e.shadow;
  $("#pol-sticky").checked = !!st.enabled;
  $("#pol-sticky-ttl").value = st.ttl_minutes ?? 30;
  // The server stores this as policy.pricing.allow_reference_estimates; a
  // top-level `allow_estimates` key is dropped by normalize_policy, so the
  // checkbox used to look saved while the policy never changed.
  $("#pol-allow-estimates").checked = (p.pricing || {}).allow_reference_estimates === true;
  const escOff = $("#pol-esc-mode").value === "off";
  ["#pol-esc-threshold", "#pol-esc-max", "#pol-esc-to", "#pol-esc-shadow"].forEach((sel) => {
    $(sel).disabled = escOff;
  });
}

function readPolicyForm() {
  const p = JSON.parse(JSON.stringify(currentPolicy()));
  const num = (sel, dflt) => {
    const v = parseInt($(sel).value, 10);
    return Number.isFinite(v) ? v : dflt;
  };
  p.fallback = { ...(p.fallback || {}), enabled: $("#pol-fallback-enabled").checked, max_attempts: num("#pol-fallback-max", 5) };
  p.balanced_min_quality = num("#pol-min-quality", 0);
  p.gated = {
    ...(p.gated || {}),
    hard_on_tools: $("#pol-gated-tools").checked,
    hard_on_vision: $("#pol-gated-vision").checked,
    hard_on_min_messages: num("#pol-gated-messages", 8),
    hard_on_min_prompt_chars: num("#pol-gated-chars", 6000),
    allow_mundane_fallback: $("#pol-gated-mundane-fallback").checked,
  };
  p.escalation = {
    ...(p.escalation || {}),
    mode: $("#pol-esc-mode").value,
    failure_threshold: num("#pol-esc-threshold", 2),
    max_per_conversation: num("#pol-esc-max", 2),
    to_pool: $("#pol-esc-to").value,
    shadow: $("#pol-esc-shadow").checked,
  };
  p.stickiness = { enabled: $("#pol-sticky").checked, ttl_minutes: num("#pol-sticky-ttl", 30) };
  p.pricing = { ...(p.pricing || {}), allow_reference_estimates: $("#pol-allow-estimates").checked };
  delete p.allow_estimates;
  return p;
}

async function savePolicy(policy, { quiet = false } = {}) {
  const status = $("#pol-status");
  try {
    state.routing = await api("/v1/routing", { method: "PUT", body: JSON.stringify({ policy }) });
    renderRouting();
    if (status) { status.textContent = "Saved."; status.className = "auth-status ok"; }
    if (!quiet) toast(t("toast.policy_saved"), "ok");
    return true;
  } catch (err) {
    if (status) { status.textContent = err.message; status.className = "auth-status"; }
    toast(err.message, "err");
    return false;
  }
}

function bindPolicyForm() {
  const form = $("#routing-policy-form");
  if (!form) return;
  const markDirty = () => { form.dataset.dirty = "1"; };
  form.addEventListener("input", markDirty);
  form.addEventListener("change", markDirty);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("#pol-save");
    btn.disabled = true;
    const policy = readPolicyForm();
    form.dataset.dirty = "";
    if (!(await savePolicy(policy))) form.dataset.dirty = "1";
    btn.disabled = false;
  });
  $("#pol-esc-mode").addEventListener("change", () => {
    const off = $("#pol-esc-mode").value === "off";
    ["#pol-esc-threshold", "#pol-esc-max", "#pol-esc-to", "#pol-esc-shadow"].forEach((sel) => {
      $(sel).disabled = off;
    });
  });
}

/* ─── pool picker (searchable, paginated — scales to hundreds of models) ─── */
const POOL_PAGE = 25;
const POOL_NAMES = { mundane: "Mundane", hard: "Hard", fallback: "Fallback" };
const AVAILABILITY_LABEL = {
  auto: "Auto", pinned_only: "Pinned only", unpriced: "No price", not_deployable: "No key", estimate_only: "Est. price",
};

async function loadPoolModels() {
  const q = ($("#pool-search")?.value || "").trim();
  const scope = $("#pool-scope")?.value || "routable";
  const offset = state.poolOffset || 0;
  try {
    state.poolModels = await api(
      `/api/routing/models?scope=${encodeURIComponent(scope)}&q=${encodeURIComponent(q)}&limit=${POOL_PAGE}&offset=${offset}`
    );
  } catch (e) {
    state.poolModels = { total: 0, models: [] };
    toast(tf("toast.load_models_failed", {msg: e.message}), "err");
  }
}

function fmtPrice(v) {
  if (v === null || v === undefined) return '<span class="muted" title="Price unknown — not treated as free">unknown</span>';
  return `$${v < 0.01 ? v.toFixed(4) : v.toFixed(2)}`;
}

function capSummary(m) {
  const caps = [];
  const keys = ["tools", "vision", "json", "json_schema"];
  const labels = { tools: "Tools", vision: "Vision", json: "JSON mode", json_schema: "JSON schema" };
  for (const key of keys) if (m[key] === true) caps.push(`<span class="cap-pill">${labels[key]}</span>`);
  if (caps.length) return caps.join("");
  // Absence of evidence is not evidence of absence: when no capability is
  // confirmed but at least one is unknown (null), say Unknown instead of
  // implying the model supports nothing.
  if (keys.some((key) => m[key] === null || m[key] === undefined)) {
    return `<span class="muted small">${escapeHtml(t("providers.cap_unknown"))}</span>`;
  }
  return '<span class="muted small">none</span>';
}

function renderPoolTable() {
  const tbody = $("#pool-models-table tbody");
  if (!tbody) return;
  const data = state.poolModels || { total: 0, models: [] };
  const pools = currentPolicy().pools || {};
  if (!data.models.length) {
    tbody.innerHTML = `<tr><td colspan="6"><div class="empty-inline">No models match. Register models under <a href="#" data-go-tab="providers">Providers</a>.</div></td></tr>`;
  } else {
    tbody.innerHTML = data.models.map((m) => {
      const toggles = ["mundane", "hard", "fallback"].map((pool) => {
        const on = (pools[pool] || []).includes(m.id);
        return `<button type="button" class="pool-toggle tier-${pool}${on ? " on" : ""}" data-pool-toggle="${pool}" data-model="${escapeHtml(m.id)}" aria-pressed="${on}" title="${on ? "Remove from" : "Add to"} ${POOL_NAMES[pool]}">${POOL_NAMES[pool]}</button>`;
      }).join("");
      return `<tr>
        <td><code>${escapeHtml(m.id)}</code><div class="muted small">${escapeHtml(m.provider || "")}</div></td>
        <td>${capSummary(m)}</td>
        <td>${m.context_length ? fmtNum(m.context_length) : '<span class="muted">—</span>'}</td>
        <td>${fmtPrice(m.input_per_million)} · ${fmtPrice(m.output_per_million)}</td>
        <td><span class="status-chip avail-${m.availability}">${AVAILABILITY_LABEL[m.availability] || m.availability}</span></td>
        <td class="th-actions"><div class="pool-toggles">${toggles}</div></td>
      </tr>`;
    }).join("");
  }
  const offset = state.poolOffset || 0;
  const shownTo = Math.min(offset + data.models.length, data.total);
  $("#pool-count").textContent = data.total
    ? `${offset + 1}–${shownTo} of ${fmtNum(data.total)} models` : "0 models";
  $("#pool-prev").disabled = offset <= 0;
  $("#pool-next").disabled = offset + POOL_PAGE >= data.total;
}

function renderPoolChips() {
  const pools = currentPolicy().pools || {};
  // Entries that no longer name a registered model (removed, or the provider
  // was re-created under another slug). Routing ignores them; mark them so
  // the operator can see why a pool is effectively empty and remove them.
  const stale = new Set(state.routing?.stale_models || []);
  ["mundane", "hard", "fallback"].forEach((pool) => {
    const wrap = $(`[data-pool-chips="${pool}"]`);
    if (!wrap) return;
    const ids = pools[pool] || [];
    wrap.innerHTML = ids.length
      ? ids.map((id) => {
          const gone = stale.has(id);
          const note = gone ? " — not a registered model; ignored by routing" : "";
          return `<span class="model-chip tier-${pool}${gone ? " is-stale" : ""}" title="${escapeHtml(id + note)}"><span class="chip-id">${escapeHtml(id)}</span>${gone ? '<span class="chip-stale">not registered</span>' : ""}<button type="button" class="chip-x" data-pool-remove="${pool}" data-model="${escapeHtml(id)}" aria-label="Remove ${escapeHtml(id)} from ${POOL_NAMES[pool]}${escapeHtml(note)}">×</button></span>`;
        }).join("")
      : `<span class="muted small">Empty — add models from the table below.</span>`;
  });
}

async function togglePool(pool, modelId, add) {
  const policy = JSON.parse(JSON.stringify(currentPolicy()));
  const list = new Set(policy.pools[pool] || []);
  if (add) list.add(modelId); else list.delete(modelId);
  policy.pools[pool] = [...list];
  if (await savePolicy(policy, { quiet: true })) {
    renderPoolTable();
  }
}

let _poolSearchTimer = null;
function bindPoolPicker() {
  const search = $("#pool-search");
  if (!search) return;
  search.addEventListener("input", () => {
    clearTimeout(_poolSearchTimer);
    _poolSearchTimer = setTimeout(async () => {
      state.poolOffset = 0;
      await loadPoolModels();
      renderPoolTable();
    }, 200);
  });
  $("#pool-scope").addEventListener("change", async () => {
    state.poolOffset = 0;
    await loadPoolModels();
    renderPoolTable();
  });
  $("#pool-prev").addEventListener("click", async () => {
    state.poolOffset = Math.max(0, (state.poolOffset || 0) - POOL_PAGE);
    await loadPoolModels();
    renderPoolTable();
  });
  $("#pool-next").addEventListener("click", async () => {
    state.poolOffset = (state.poolOffset || 0) + POOL_PAGE;
    await loadPoolModels();
    renderPoolTable();
  });
  // Delegated: rows re-render on every page change.
  document.addEventListener("click", (e) => {
    const t = e.target.closest("[data-pool-toggle]");
    if (t) {
      togglePool(t.dataset.poolToggle, t.dataset.model, t.getAttribute("aria-pressed") !== "true");
      return;
    }
    const r = e.target.closest("[data-pool-remove]");
    if (r) togglePool(r.dataset.poolRemove, r.dataset.model, false);
  });
}

/* ─── explain (dry-run) ─── */
function bindExplain() {
  const form = $("#explain-form");
  if (!form) return;
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const params = new URLSearchParams({
      tools: $("#ex-tools").checked, vision: $("#ex-vision").checked,
      json: $("#ex-json").checked, messages: $("#ex-messages").value || "1",
      prompt_chars: $("#ex-chars").value || "0", escalate: $("#ex-escalate").checked,
    });
    const out = $("#explain-result");
    out.innerHTML = '<span class="muted small">Evaluating…</span>';
    try {
      const r = await api(`/api/routing/explain?${params}`);
      renderExplain(r);
    } catch (err) {
      out.innerHTML = `<div class="callout callout-warn"><p class="card-sub">${escapeHtml(err.message)}</p></div>`;
    }
  });
}

function renderExplain(r) {
  const out = $("#explain-result");
  const stages = (r.stages || []).map((s) =>
    `<li><span class="stage-name">${escapeHtml(s.stage.replaceAll("_", " "))}</span><strong>${s.count}</strong></li>`
  ).join("");
  const tier = r.tier ? `<span class="tier-chip tier-${escapeHtml(r.tier)}">${escapeHtml(r.tier)}</span>` : "";
  const head = r.ok
    ? `<div class="explain-head ok"><span class="status-chip avail-auto">Selected</span> <code>${escapeHtml(r.selected)}</code> ${tier}</div>
       <p class="card-sub">${escapeHtml(r.reason || "")}</p>
       ${r.fallbacks && r.fallbacks.length ? `<p class="card-sub">Fallbacks: ${r.fallbacks.map((f) => `<code>${escapeHtml(f)}</code>`).join(" → ")}</p>` : ""}
       <p class="card-sub muted">Strategy: ${escapeHtml(r.strategy)} (ran as ${escapeHtml(r.effective_strategy)}) · ${r.candidate_count} eligible</p>`
    : `<div class="explain-head err"><span class="status-chip avail-not_deployable">No candidate</span> <code>${escapeHtml(r.diagnosis || "")}</code></div>
       <p class="card-sub">${escapeHtml(r.message || "")}</p>
       ${(r.exclusions || []).length ? `<ul class="exclusion-list">${r.exclusions.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul>` : ""}`;
  const notes = (r.notes || []).length
    ? `<ul class="routing-notes">${r.notes.map((n) => `<li>${escapeHtml(n)}</li>`).join("")}</ul>` : "";
  out.innerHTML = `${head}${notes}
    <p class="card-sub muted">Request: needs ${escapeHtml((r.needs || []).join(", ") || "nothing")} · ~${r.estimated_prompt_tokens} tokens · classified <strong>${escapeHtml(r.difficulty?.tier || "")}</strong>${r.difficulty?.signals?.length ? ` (${escapeHtml(r.difficulty.signals.join(", "))})` : ""}</p>
    <ol class="stage-list">${stages}</ol>`;
}

/* ==========================================================================
   ANALYTICS
   ========================================================================== */
async function loadAnalytics() {
  const days = state.windowDays;
  try {
    const [recent, spend, latency, savings] = await Promise.all([
      api(`/v1/analytics/recent?limit=50`),
      api(`/v1/analytics/spend?days=${days}`),
      api(`/v1/analytics/latency?days=${days}`),
      api(`/v1/analytics/savings?days=${days}&baseline=gpt-4o`).catch(() => null),
    ]);
    state.recent = recent.items || [];
    state.spend = spend;
    state.latency = latency;
    if (savings) state.savings = savings;
    await loadRoutingAnalytics();
  } catch (e) {
    toast(tf("toast.load_analytics_failed", {msg: e.message}), "err");
  }
}

function renderAnalytics() {
  renderRoutingAnalytics();
  // Spend summary
  const totalReq = state.spend.by_model.reduce((a, m) => a + m.request_count, 0);
  $("#spend-summary").innerHTML =
    `Last <strong>${state.spend.days || state.windowDays}d</strong> · ` +
    `<strong>${fmtUsd(state.spend.total_microcents)}</strong> across ` +
    `<strong>${fmtNum(totalReq)}</strong> requests`;

  // Bar chart
  const chart = $("#bar-chart");
  if (!state.spend.by_model.length) {
    chart.innerHTML = `<div class="empty-mini">
      <p>No spend data yet for this window.</p>
      <p class="muted">Send a request through <code>/v1/chat/completions</code> to see your costs here.</p>
    </div>`;
  } else {
    const max = Math.max(...state.spend.by_model.map((m) => m.cost_microcents)) || 1;
    chart.innerHTML = state.spend.by_model.slice(0, 10).map((m) => {
      const pct = Math.max(2, (m.cost_microcents / max) * 100);
      return `
        <div class="bar-row" data-tooltip="${fmtNum(m.request_count)} requests, ${fmtUsd(m.cost_microcents)}">
          <div class="bar-label">${escapeHtml(m.model || "—")}</div>
          <div class="bar-track"><div class="bar-fill" style="right:${100 - pct}%"></div></div>
          <div class="bar-value">${fmtUsd(m.cost_microcents)} <span class="reqs">${fmtNum(m.request_count)} req</span></div>
        </div>`;
    }).join("");
  }

  // Latency table
  const lt = $("#latency-table tbody");
  if (!state.latency.by_provider.length) {
    lt.innerHTML = `<tr><td colspan="4" class="muted" style="text-align:center;padding:24px">No data yet for this window.</td></tr>`;
  } else {
    lt.innerHTML = state.latency.by_provider.map((p) => `
      <tr class="row-in">
        <td><strong>${escapeHtml(p.provider)}</strong></td>
        <td>${fmtNum(p.request_count)}</td>
        <td>${fmtNum(p.p50_ms)} ms</td>
        <td>${fmtNum(p.p99_ms)} ms</td>
      </tr>
    `).join("");
  }

  // Recent table
  const rt = $("#recent-table tbody");
  const rEmpty = $("#recent-empty");
  if (!state.recent.length) {
    rt.innerHTML = "";
    rEmpty.hidden = false;
    rEmpty.classList.add("shown");
  } else {
    rEmpty.hidden = true;
    rEmpty.classList.remove("shown");
    rt.innerHTML = state.recent.map((it) => {
      const ok = (it.status_code || 0) < 400;
      const pillCls = ok ? "ok" : "err";
      const pillTxt = ok ? `${it.status_code} OK` : `${it.status_code} ${it.error_type || "error"}`;
      return `
        <tr class="row-in copy-row" data-trace="${escapeHtml(it.trace_id || "")}" data-tooltip="Click to copy trace ID">
          <td>${fmtTime(it.created_at)}</td>
          <td><code>${escapeHtml(it.routed_model || it.model_resolved || it.model_requested || "—")}</code>${it.cost_unknown ? ' <span class="status-chip avail-unpriced" title="Tokens were used but no price is configured">cost unknown</span>' : ""}</td>
          <td>${routingCell(it)}</td>
          <td>${escapeHtml(it.provider || "—")}</td>
          <td>${fmtNum(it.input_tokens)} / ${fmtNum(it.output_tokens)}</td>
          <td>${fmtNum(it.latency_ms)} ms</td>
          <td><span class="pill ${pillCls}">${escapeHtml(pillTxt)}</span></td>
        </tr>`;
    }).join("");
    $$(".copy-row").forEach((row) =>
      row.addEventListener("click", () => {
        const tid = row.dataset.trace;
        if (tid) copyToClipboard(tid);
      })
    );
  }
}

const TIER_LABEL = {
  mundane: "Mundane", hard: "Hard", fallback: "Fallback",
  escalated: "Escalated", untiered: "Untiered",
};

/** Routing column for the recent-requests table. Text label + color. */
function routingCell(it) {
  if (it.model_requested !== "auto") return '<span class="muted small">pinned</span>';
  const bits = [];
  if (it.routing_tier) {
    const tier = it.routing_tier === "escalated" ? "frontier" : it.routing_tier;
    bits.push(`<span class="tier-chip tier-${escapeHtml(tier)}">${escapeHtml(TIER_LABEL[it.routing_tier] || it.routing_tier)}</span>`);
  } else {
    bits.push(`<span class="tier-chip tier-adaptive">${escapeHtml(it.routing_strategy || "auto")}</span>`);
  }
  if (it.fallback_used) bits.push('<span class="tier-chip tier-fallback">fallback</span>');
  if (it.escalated) bits.push('<span class="tier-chip tier-frontier">escalated</span>');
  const title = it.routing_reason ? ` title="${escapeHtml(it.routing_reason)}"` : "";
  return `<span class="routing-cell"${title}>${bits.join(" ")}</span>`;
}

async function loadRoutingAnalytics() {
  try {
    loadBaselineOptions();
    state.routingAnalytics = await api(`/v1/analytics/routing?days=${state.windowDays}`);
  } catch (e) {
    state.routingAnalytics = null;
  }
}

function _raBars(listSel, rows, labelKey, colorFor) {
  const el = $(listSel);
  if (!el) return;
  if (!rows.length) { el.innerHTML = '<li class="muted small">No data in this window.</li>'; return; }
  const max = Math.max(...rows.map((r) => r.requests)) || 1;
  el.innerHTML = rows.map((r) => {
    const label = r[labelKey] || "—";
    const pct = Math.max(3, Math.round((r.requests / max) * 100));
    return `<li class="ra-bar">
      <span class="ra-bar-label">${escapeHtml(TIER_LABEL[label] || label)}</span>
      <span class="ra-bar-track"><span class="ra-bar-fill ${colorFor(label)}" style="width:${pct}%"></span></span>
      <span class="ra-bar-value">${fmtNum(r.requests)}</span>
    </li>`;
  }).join("");
}

function renderRoutingAnalytics() {
  const d = state.routingAnalytics;
  const k = $("#ra-kpis");
  if (!k) return;
  if (!d) { k.innerHTML = `<p class="muted small">${escapeHtml(t("js.ra_unavailable"))}</p>`; return; }
  const pct = (n) => (d.requests ? `${Math.round((n / d.requests) * 100)}%` : "0%");
  k.innerHTML = [
    ["Auto requests", fmtNum(d.auto_requests), pct(d.auto_requests), "tier-adaptive"],
    ["Fallbacks", fmtNum(d.fallback_requests), pct(d.fallback_requests), "tier-fallback"],
    ["Escalations", fmtNum(d.escalated_requests), pct(d.escalated_requests), "tier-frontier"],
    ["Errors", fmtNum(d.error_requests), pct(d.error_requests), "tier-error"],
    ["Cost unknown", fmtNum(d.unknown_cost_requests), "requests with no price", "tier-inactive"],
  ].map(([label, value, sub, cls]) =>
    `<div class="ra-kpi ${cls}"><span class="ra-kpi-label">${label}</span><strong>${value}</strong><span class="muted small">${sub}</span></div>`
  ).join("");
  $("#ra-summary").textContent =
    `Last ${d.days}d · ${fmtNum(d.requests)} requests · ${fmtUsd(d.cost_microcents)} recorded cost`;

  const tl = $("#ra-timeline");
  const note = $("#ra-timeline-note");
  const days = d.timeline || [];
  if (!days.length) {
    tl.innerHTML = '<p class="muted small">No requests in this window.</p>';
    if (note) note.hidden = true;
  } else {
    const max = Math.max(...days.map((x) => x.requests)) || 1;
    // A handful of requests makes a "chart" that implies a trend it cannot
    // support. Say so rather than letting two bars suggest a pattern.
    const totalReq = days.reduce((a, x) => a + x.requests, 0);
    if (note) {
      if (totalReq < 5) {
        note.hidden = false;
        note.textContent = `${totalReq} request${totalReq === 1 ? "" : "s"} in this window — too few to show a trend.`;
      } else {
        note.hidden = true;
      }
    }
    tl.innerHTML = days.map((x) => {
      const h = Math.max(4, Math.round((x.requests / max) * 100));
      const ah = x.requests ? Math.round((x.auto / x.requests) * h) : 0;
      return `<div class="ra-col" title="${escapeHtml(x.day)}: ${x.requests} requests (${x.auto} auto, ${x.errors} errors)">
        <div class="ra-col-bar" style="height:${h}%"><div class="ra-col-auto" style="height:${h ? Math.round((ah / h) * 100) : 0}%"></div></div>
        <span class="ra-col-label">${escapeHtml(x.day.slice(5))}</span>
      </div>`;
    }).join("");
  }
  const tierClass = (t) => `tier-${t === "escalated" ? "frontier" : (t === "untiered" ? "inactive" : t)}`;
  _raBars("#ra-tiers", d.by_tier || [], "tier", tierClass);
  _raBars("#ra-strategies", d.by_strategy || [], "strategy",
    (s) => ({ balanced: "tier-balanced", adaptive: "tier-adaptive", adaptive_gated: "tier-frontier",
              cheapest: "tier-fallback", quality: "tier-hard" }[s] || "tier-inactive"));
  _raBars("#ra-models", (d.by_model || []).slice(0, 8), "model", () => "tier-adaptive");
  renderRoutingAnalyticsExtra(d);
}

function bindWindowSeg() {
  $$("#window-seg .seg-btn").forEach((b) =>
    b.addEventListener("click", async () => {
      $$("#window-seg .seg-btn").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      state.windowDays = parseInt(b.dataset.days, 10);
      await loadAnalytics();
      renderAnalytics();
      renderOverview();
    })
  );
}

/* ==========================================================================
   KEYS
   ========================================================================== */
async function loadKeys() {
  try {
    const data = await api("/v1/keys");
    state.keys = data.keys || [];
  } catch (e) {
    toast(tf("toast.load_keys_failed", {msg: e.message}), "err");
  }
}

function _keyStatusPill(k) {
  if (k.expired) return '<span class="pill err">Expired</span>';
  return k.is_active
    ? '<span class="pill ok">Active</span>'
    : '<span class="pill muted">Revoked</span>';
}

function renderKeys() {
  const tbody = $("#keys-table tbody");
  const empty = $("#keys-empty");
  tbody.innerHTML = "";
  const keys = state.keys || [];
  if (empty) empty.hidden = keys.length > 0;
  if (!keys.length) return;

  keys.forEach((k) => {
    const tr = document.createElement("tr");
    tr.className = "row-in";
    // A revoked or expired key has no actions: rotation exists to replace it,
    // and there is nothing left to revoke.
    const usable = k.is_active && !k.expired;
    const actions = usable
      ? `
        <button class="btn btn-ghost btn-sm rename-key" data-id="${escapeHtml(k.id)}" data-name="${escapeHtml(k.name)}">Rename</button>
        <button class="btn btn-ghost btn-sm rotate-key" data-id="${escapeHtml(k.id)}" data-name="${escapeHtml(k.name)}">Rotate</button>
        <button class="btn btn-ghost btn-sm btn-danger rev-key" data-id="${escapeHtml(k.id)}" data-name="${escapeHtml(k.name)}">Revoke</button>`
      : `<span class="muted small">${k.expired ? "expired" : "revoked"}</span>`;
    tr.innerHTML = `
      <td><strong>${escapeHtml(k.name)}</strong></td>
      <td><code>${escapeHtml(k.key_prefix)}</code></td>
      <td>${_keyStatusPill(k)}</td>
      <td>${k.created_at ? fmtTime(k.created_at) : "—"}</td>
      <td>${k.last_used_at ? fmtTime(k.last_used_at) : '<span class="muted">Never</span>'}</td>
      <td>${k.expires_at ? fmtDate(k.expires_at) : '<span class="muted">Never</span>'}</td>
      <td class="th-actions">${actions}</td>
    `;
    tbody.appendChild(tr);
  });

  $$(".rev-key").forEach((b) =>
    b.addEventListener("click", async () => {
      if (!confirm(tf("confirm.revoke", {name: b.dataset.name}))) return;
      try {
        await api(`/v1/keys/${b.dataset.id}`, { method: "DELETE" });
        toast(tf("toast.revoked", {name: b.dataset.name}), "ok");
        await loadKeys();
        renderKeys();
      } catch (e) {
        toast(e.message, "err");
      }
    })
  );

  $$(".rename-key").forEach((b) =>
    b.addEventListener("click", async () => {
      const next = prompt(tf("prompt.rename_key", {name: b.dataset.name}), b.dataset.name);
      if (next === null) return;
      const name = next.trim();
      if (!name) { toast(t("toast.name_empty"), "err"); return; }
      try {
        await api(`/v1/keys/${b.dataset.id}`, { method: "PUT", body: JSON.stringify({ name }) });
        toast(t("toast.key_renamed"), "ok");
        await loadKeys();
        renderKeys();
      } catch (e) {
        toast(e.message, "err");
      }
    })
  );

  $$(".rotate-key").forEach((b) =>
    b.addEventListener("click", async () => {
      const revoke = confirm(tf("confirm.rotate", {name: b.dataset.name}));
      try {
        const r = await api(`/v1/keys/${b.dataset.id}/rotate`, {
          method: "POST",
          body: JSON.stringify({ revoke_original: revoke }),
        });
        showNewKey(r.api_key, r.name, revoke
          ? "The previous key was revoked."
          : "The previous key still works until you revoke it.");
        await loadKeys();
        renderKeys();
      } catch (e) {
        toast(e.message, "err");
      }
    })
  );
}

function showNewKey(secret, name, note) {
  const display = $("#new-key-display");
  if (!display) return;
  $("#new-key-value").textContent = secret;
  const caption = $("#new-key-caption");
  if (caption) {
    caption.textContent = `“${name}” — ${note || ""} Copy it now; it is stored only as a hash and cannot be shown again.`;
  }
  // OpenCode / OpenAI-SDK ready snippet, built from this page's origin so it
  // is correct for whatever host and port the operator actually uses.
  const base = `${location.origin}/v1`;
  const snippet = $("#new-key-snippet");
  if (snippet) {
    snippet.textContent =
      `export OPENAI_BASE_URL="${base}"\nexport OPENAI_API_KEY="${secret}"`;
  }
  display.hidden = false;
  $("#new-key-copy").onclick = (ev) => copyToClipboard(secret, ev.currentTarget);
  const sc = $("#new-key-snippet-copy");
  if (sc) sc.onclick = (ev) => copyToClipboard(snippet.textContent, ev.currentTarget);
  display.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function bindKeyForm() {
  $("#key-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = $("#key-name").value.trim();
    if (!name) { toast(t("toast.name_first"), "err"); return; }
    const daysRaw = $("#key-expiry") ? $("#key-expiry").value : "";
    const payload = { name };
    if (daysRaw) payload.expires_in_days = parseInt(daysRaw, 10);
    const btn = $("#key-create-btn");
    if (btn) btn.disabled = true;
    try {
      const r = await api("/v1/keys", { method: "POST", body: JSON.stringify(payload) });
      $("#key-name").value = "";
      if ($("#key-expiry")) $("#key-expiry").value = "";
      showNewKey(
        r.api_key,
        r.name,
        r.expires_at ? `Expires ${fmtDate(r.expires_at)}.` : "This key does not expire."
      );
      toast(tf("toast.created", {name}), "ok");
      await loadKeys();
      renderKeys();
    } catch (err) {
      toast(err.message, "err");
    } finally {
      if (btn) btn.disabled = false;
    }
  });
}

/* ==========================================================================
   SECURITY  (administrator account, password, sessions)
   ========================================================================== */
async function loadSecurity() {
  try {
    const data = await api("/api/auth/sessions");
    state.security = data;
  } catch (e) {
    toast(tf("toast.load_security_failed", {msg: e.message}), "err");
  }
}

function renderSecurity() {
  const data = state.security;
  if (!data) return;
  const acct = data.account || {};

  $("#sec-username").textContent = acct.username || "—";
  $("#sec-password-changed").textContent = acct.password_changed_at
    ? fmtDate(acct.password_changed_at) : "—";
  $("#sec-last-login").textContent = acct.last_login_at
    ? fmtDate(acct.last_login_at) : "—";

  const current = (data.sessions || []).find((s) => s.current);
  $("#sec-session").textContent = current
    ? `Active, expires ${fmtDate(current.expires_at)}`
    : "Active";

  // A CLI reset is worth surfacing loudly: it is the one way the password can
  // change without going through this screen.
  const notice = $("#sec-reset-notice");
  if (acct.password_reset_at && notice) {
    notice.hidden = false;
    $("#sec-reset-when").textContent = fmtDate(acct.password_reset_at);
  } else if (notice) {
    notice.hidden = true;
  }

  const tbody = $("#sessions-table tbody");
  tbody.innerHTML = "";
  (data.sessions || []).forEach((s) => {
    const tr = document.createElement("tr");
    tr.className = "row-in";
    tr.innerHTML = `
      <td>${s.current ? '<span class="pill ok">This device</span>' : escapeHtml(_uaLabel(s.user_agent))}</td>
      <td><code>${escapeHtml(s.ip_address || "—")}</code></td>
      <td>${s.last_seen_at ? fmtTime(s.last_seen_at) : "—"}</td>
      <td>${s.expires_at ? fmtDate(s.expires_at) : "—"}</td>
    `;
    tbody.appendChild(tr);
  });
}

/** Reduce a User-Agent to something recognizable without fingerprinting. */
function _uaLabel(ua) {
  if (!ua) return "Unknown device";
  const browsers = [
    [/Firefox\/(\d+)/, "Firefox"],
    [/Edg\/(\d+)/, "Edge"],
    [/Chrome\/(\d+)/, "Chrome"],
    [/Version\/(\d+).*Safari/, "Safari"],
    [/curl\/([\d.]+)/, "curl"],
  ];
  for (const [re, name] of browsers) {
    const m = ua.match(re);
    if (m) return `${name} ${m[1]}`;
  }
  return "Browser";
}

async function changePassword(e) {
  e.preventDefault();
  const current_password = $("#pw-current").value;
  const new_password = $("#pw-new").value;
  const confirm_password = $("#pw-confirm").value;
  if (new_password !== confirm_password) {
    setAuthStatus("#pw-status", t("auth.new_pw_mismatch"), "err");
    return;
  }
  if (!current_password || !new_password) {
    setAuthStatus("#pw-status", t("auth.fill_three"), "err");
    return;
  }
  setAuthStatus("#pw-status", "");
  if ($("#pw-submit")) $("#pw-submit").disabled = true;
  try {
    const r = await api("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password, confirm_password }),
    });
    $("#pw-current").value = "";
    $("#pw-new").value = "";
    $("#pw-confirm").value = "";
    setAuthStatus("#pw-status", r.message || "Password updated.", "ok");
    toast(t("toast.password_updated"), "ok");
    await loadSecurity();
    renderSecurity();
  } catch (err) {
    setAuthStatus("#pw-status", err.message, "err");
  } finally {
    if ($("#pw-submit")) $("#pw-submit").disabled = false;
  }
}

function bindSecurity() {
  $("#password-form")?.addEventListener("submit", changePassword);
  $("#revoke-others-btn")?.addEventListener("click", async () => {
    if (!confirm(t("confirm.sign_out_others"))) return;
    try {
      const r = await api("/api/auth/sessions/revoke-others", { method: "POST" });
      setAuthStatus("#sessions-status", `Signed out ${r.revoked} other session(s).`, "ok");
      await loadSecurity();
      renderSecurity();
    } catch (e) {
      setAuthStatus("#sessions-status", e.message, "err");
    }
  });
}

/* ==========================================================================
   QUALITY (AA Intelligence Index + manual overrides)
   ========================================================================== */
/* One loader for the whole Quality page. Concurrent callers share the same
   in-flight request, so opening the page (or switching its in-page tabs) never
   fires duplicate /v1/quality requests. Switching in-page tabs does not load
   anything at all: every pane is rendered from the same state. */
let qualityLoadInFlight = null;
function refreshQualityPage() {
  if (qualityLoadInFlight) return qualityLoadInFlight;
  qualityLoadInFlight = Promise.all([loadQuality(), loadQualityPreview(), loadQualityKey()])
    .then(() => {
      renderQuality();
      renderQualityPreview();
    })
    .finally(() => { qualityLoadInFlight = null; });
  return qualityLoadInFlight;
}

const QUALITY_TABS = ["models", "scores", "aa"];

function setQualityTab(name, { focus = false } = {}) {
  if (!QUALITY_TABS.includes(name)) name = "models";
  state.qualityTab = name;
  for (const id of QUALITY_TABS) {
    const tab = document.querySelector(`[data-q-tab="${id}"]`);
    const pane = document.getElementById(`q-pane-${id}`);
    const on = id === name;
    if (tab) {
      tab.setAttribute("aria-selected", on ? "true" : "false");
      tab.tabIndex = on ? 0 : -1;
      if (on && focus) tab.focus();
    }
    // `hidden` keeps every pane in the DOM: typed values, ticked rows and an
    // open key form survive switching away and back.
    if (pane) pane.hidden = !on;
  }
}

function bindQualityTabs() {
  const list = $("#quality-tabs");
  if (!list || list.dataset.bound) return;
  list.dataset.bound = "1";
  list.addEventListener("click", (e) => {
    const tab = e.target.closest("[data-q-tab]");
    if (tab) setQualityTab(tab.dataset.qTab);
  });
  // WAI-ARIA tabs pattern: arrows move between tabs, Home/End jump to the ends.
  list.addEventListener("keydown", (e) => {
    const current = QUALITY_TABS.indexOf(state.qualityTab || "models");
    let next = null;
    if (e.key === "ArrowRight") next = (current + 1) % QUALITY_TABS.length;
    else if (e.key === "ArrowLeft") next = (current - 1 + QUALITY_TABS.length) % QUALITY_TABS.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = QUALITY_TABS.length - 1;
    if (next === null) return;
    e.preventDefault();
    setQualityTab(QUALITY_TABS[next], { focus: true });
  });
  setQualityTab(state.qualityTab || "models");
}

/* Tab-label status indicators. The Artificial Analysis dot reflects credential
   and connection-test state; a failed benchmark sync is flagged on the
   "Quality scores" tab and, when the connection itself is fine, also turns
   the AA dot amber, but never claims "Connected" for an untested key. */
function renderQualityTabIndicators() {
  const key = state.qualityKey || {};
  const conn = key.connection_status || "not_configured";
  const syncFailed = key.sync_status === "sync_failed";

  const aaState = conn === "connected" && syncFailed ? "sync_failed" : conn;
  const dot = $("#q-tab-aa-dot");
  if (dot) dot.dataset.state = aaState;
  const parts = [t(`qa.status.${conn}`)];
  if (syncFailed) parts.push(t("qa.sync.sync_failed"));
  const label = `${t("q.tab_aa")}: ${parts.join(", ")}`;
  const aaSr = $("#q-tab-aa-sr");
  if (aaSr) aaSr.textContent = ` (${parts.join(", ")})`;
  const aaTab = $("#q-tab-aa");
  if (aaTab) aaTab.title = label;

  const flag = $("#q-tab-scores-flag");
  if (flag) flag.hidden = !syncFailed;
  const scSr = $("#q-tab-scores-sr");
  if (scSr) scSr.textContent = syncFailed ? ` (${t("qa.sync.sync_failed")})` : "";
  const scTab = $("#q-tab-scores");
  if (scTab) scTab.title = syncFailed ? `${t("q.tab_scores")}: ${t("qa.sync.sync_failed")}` : "";
}

async function loadQuality() {
  try {
    const data = await api("/v1/quality");
    state.quality = data;
  } catch (e) {
    toast(tf("toast.load_quality_failed", {msg: e.message}), "err");
  }
}

async function loadQualityKey() {
  try {
    state.qualityKey = await api("/v1/quality/key");
  } catch (e) {
    // Non-fatal: the scores table still renders, the provenance block shows "—".
    state.qualityKey = null;
  }
}

async function loadQualityPreview() {
  try {
    state.qualityPreview = await api("/v1/quality/auto-preview");
  } catch (e) {
    state.qualityPreview = null;
  }
}

function renderQuality() {
  const aa = state.quality?.aa_index || {};
  const key = state.qualityKey || {};

  const sourceLabel = {
    "live":         `<span class="pill ok">${escapeHtml(t("q.src.live"))}</span>`,
    "stale-cache":  `<span class="pill warn">${escapeHtml(t("q.src.stale_cache"))}</span>`,
    "stale-db":     `<span class="pill warn">${escapeHtml(t("q.src.stale_db"))}</span>`,
    "error":        `<span class="pill err">${escapeHtml(t("q.src.error"))}</span>`,
    "missing-key":  `<span class="pill muted">${escapeHtml(t("q.src.missing_key"))}</span>`,
  }[aa.source] || `<span class="pill">${escapeHtml(aa.source || "—")}</span>`;
  const overrides = state.quality?.override_count || 0;
  const line = $("#quality-status-line");
  if (line) {
    line.innerHTML = `${sourceLabel} · ${escapeHtml(tf("q.status_line", {
      matched: fmtNum(aa.matched_count || 0),
      overrides: fmtNum(overrides),
    }))}`;
  }

  // Synchronization facts. Counts describe the latest successful sync, read
  // from the persisted status (not the static baseline merged into routing).
  const set = (sel, v) => { const el = $(sel); if (el) el.textContent = v; };
  const returned = key.last_sync_raw_count;
  const matched = key.last_sync_matched_count;
  set("#q-sync-last-ok", key.last_sync_at ? fmtTime(key.last_sync_at) : (key.configured ? t("qa.never") : "—"));
  set("#q-sync-last-attempt", key.last_sync_attempt_at
    ? `${fmtTime(key.last_sync_attempt_at)} · ${t(key.sync_status === "sync_failed" ? "q.sync_outcome_failed" : "q.sync_outcome_ok")}`
    : "—");
  set("#q-sync-returned", returned == null ? "—" : fmtNum(returned));
  set("#q-sync-matched", matched == null ? "—" : fmtNum(matched));
  set("#q-sync-unmatched", returned == null || matched == null ? "—" : fmtNum(Math.max(0, returned - matched)));
  set("#q-sync-overrides", fmtNum(overrides));

  const errBox = $("#q-sync-error");
  if (errBox) {
    const failed = key.sync_status === "sync_failed" && key.last_error_code;
    errBox.hidden = !failed;
    if (failed) {
      set("#q-sync-error-code", t(`qa.err.${key.last_error_code}`) || key.last_error_code);
      set("#q-sync-error-detail", key.last_error_detail || "");
    }
  }
  // Empty / not-configured explanation, never mixed up with provider setup.
  const empty = $("#q-sync-empty");
  if (empty) {
    let msg = "";
    if (!key.configured) msg = t("q.sync_need_key");
    else if (key.sync_status === "never_synced") msg = t("q.sync_never");
    else if (returned === 0) msg = t("q.sync_no_models");
    empty.textContent = msg;
    empty.hidden = !msg;
  }
  const refresh = $("#quality-refresh");
  if (refresh) refresh.disabled = !key.configured;

  renderQualityConnect();
  renderQualityProvenance();
  renderQualityTable();
  renderQualityTabIndicators();
}

const QA_STATUS_LABELS = {
  "not_configured":    { cls: "pill muted", en: "Not configured" },
  "key_configured":    { cls: "pill muted", en: "Key configured" },
  "connected":         { cls: "pill ok",    en: "Connected" },
  "connection_failed": { cls: "pill err",   en: "Connection failed" },
};

function renderQualityConnect() {
  const key = state.qualityKey || {};
  const conn = key.connection_status || "not_configured";
  const status = QA_STATUS_LABELS[conn] || QA_STATUS_LABELS.not_configured;
  const set = (sel, v) => { const el = $(sel); if (el) el.textContent = v; };

  const statusEl = $("#quality-connect-status");
  if (statusEl) {
    statusEl.className = status.cls;
    statusEl.textContent = t(`qa.status.${conn}`) || status.en;
  }
  const maskEl = $("#quality-connect-mask");
  if (maskEl) {
    if (key.configured) {
      const mask = key.key_prefix || (key.origin === "env" ? "env" : "…");
      const origin = key.origin === "env"
        ? `<span class="muted small"> · ${escapeHtml(t("qa.from_env"))}</span>`
        : "";
      const tier = key.tier
        ? `<span class="muted small"> · ${escapeHtml(tf("qa.tier", { tier: key.tier }))}</span>`
        : "";
      maskEl.innerHTML = `<code>${escapeHtml(mask)}</code>${origin}${tier}`;
    } else {
      maskEl.innerHTML = "";
    }
  }

  const removeBtn = $("#quality-connect-remove");
  if (removeBtn) removeBtn.hidden = !key.can_clear;
  const replaceBtn = $("#quality-connect-replace");
  if (replaceBtn) replaceBtn.textContent = t(key.configured ? "qa.replace" : "qa.add");
  const testBtn = $("#quality-connect-test");
  if (testBtn) testBtn.disabled = !key.configured;

  // Test and sync history only mean something once a key exists; hiding them
  // keeps the not-configured state compact.
  $$("#quality-connect-meta .qa-when-configured").forEach((el) => { el.hidden = !key.configured; });

  // Credential, latest test, last good test and sync: four separate facts.
  set("#quality-connect-credential", key.configured
    ? (key.origin === "env" ? t("qa.cred_env") : t("qa.cred_stored"))
    : t("qa.status.not_configured"));
  if (key.last_test_at) {
    const ok = key.last_test_status === "connected";
    const what = ok ? t("qa.status.connected") : (t(`qa.err.${key.last_test_status}`) || key.last_test_status);
    set("#quality-connect-test-result", `${what} · ${fmtTime(key.last_test_at)}`);
  } else {
    set("#quality-connect-test-result", key.configured ? t("qa.not_tested") : "—");
  }
  set("#quality-connect-test-ok", key.last_test_ok_at ? fmtTime(key.last_test_ok_at) : "—");
  const syncWord = t(`qa.sync.${key.sync_status || "not_configured"}`);
  set("#quality-connect-sync", key.last_sync_at ? `${syncWord} · ${fmtTime(key.last_sync_at)}` : syncWord);

  // Latest error: test failure first (it is about the connection), otherwise
  // the sync failure. Details never contain the key or an upstream body.
  const errBox = $("#quality-connect-error-box");
  const errEl = $("#quality-connect-error");
  if (errBox && errEl) {
    const testFailed = key.last_test_status && key.last_test_status !== "connected";
    const detail = testFailed ? key.last_test_detail : (key.sync_status === "sync_failed" ? key.last_error_detail : "");
    errBox.hidden = !detail;
    errEl.textContent = detail || "";
  }

  // A fresh install should land on "add a key", not on a hidden form.
  const form = $("#quality-key-form");
  if (form && !key.configured && !state.qaFormTouched) {
    form.hidden = false;
  }
}

function renderQualityKey() {
  // Backward-compatible no-op kept for any call sites; the form is now
  // rendered/controlled by renderQualityConnect + bindQualityKeyForm.
}

function renderQualityProvenance() {
  const aa = state.quality?.aa_index || {};
  const key = state.qualityKey || {};
  const set = (sel, value) => { const el = $(sel); if (el) el.textContent = value; };

  set("#quality-endpoint", aa.endpoint || "—");

  const coverage = key.last_sync_raw_count == null
    ? "—"
    : `${key.last_sync_matched_count || 0} of ${key.last_sync_raw_count} AA models matched to the catalog`;
  set("#quality-coverage", coverage);

  // The index is cached, so "last fetched" reflects the cached snapshot's age
  // rather than the process start. Only shown when AA actually answered.
  const sourceLabels = {
    "live": "live",
    "stale-cache": "cached (AA unreachable)",
    "stale-db": "cached (database snapshot)",
    "error": "failed",
    "missing-key": "no key configured",
  };
  set("#quality-fetched", sourceLabels[aa.source] || aa.source || "—");

  const originLabels = {
    "stored": `stored here (${key.key_prefix || "masked"})`,
    "env": "from ARTIFICIAL_ANALYSIS_API_KEY",
    "missing": "not configured",
  };
  set("#quality-key-origin", originLabels[key.origin] || "not configured");

  // Be explicit about where the number came from: the operator's own account
  // page outranks AA's published figure, and we say which is in use.
  const documented = aa.documented_daily_limit || key.documented_daily_limit;
  const recorded = key.recorded_daily_limit;
  set("#quality-limit",
    recorded
      ? `${recorded.toLocaleString()} requests / 24h (from your account)`
      : `${(documented || 100).toLocaleString()} requests / day (AA documented Free-tier limit)`);
}

function renderQualityTable() {
  const tbody = $("#quality-table tbody");
  tbody.innerHTML = "";
  const rows = state.quality?.models || [];
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="11" class="muted" style="text-align:center;padding:24px">
      No models in catalog.
    </td></tr>`;
    return;
  }

  const selected = qualitySelection();
  const visible = qualityFilteredRows();
  if (!visible.length) {
    tbody.innerHTML = `<tr><td colspan="11" class="muted" style="text-align:center;padding:24px">${escapeHtml(t("select.no_matches"))}</td></tr>`;
  }
  visible.slice(0, QUALITY_TABLE_LIMIT).forEach((m) => {
    const tr = document.createElement("tr");
    tr.className = "row-in";
    const aaCell = m.aa_score == null
      ? '<span class="muted">—</span>'
      : `<span title="Artificial Analysis Intelligence Index">${m.aa_score.toFixed(0)}</span>`;
    const manualCell = m.manual_score == null
      ? `<button class="btn btn-ghost btn-sm set-override" data-id="${escapeHtml(m.id)}" data-aa="${m.aa_score ?? ""}">Set</button>`
      : `<strong>${m.manual_score.toFixed(0)}</strong>`;
    const effectiveCell = m.effective_score == null
      ? '<span class="muted">unscored</span>'
      : `<strong>${m.effective_score.toFixed(0)}</strong>`;
    // TPS / TTFT come from AA latency benchmarks — null when AA hasn't
    // indexed this model on that axis. Used by the `fastest` strategy.
    const tpsCell = m.tps == null
      ? '<span class="muted">—</span>'
      : `<span title="Output tokens per second (AA median, max across reasoning variants)">${m.tps.toFixed(0)}</span>`;
    const ttftCell = m.ttft == null
      ? '<span class="muted">—</span>'
      : `<span title="Time to first token in seconds (AA median, min across variants — non-reasoning fast mode)">${m.ttft.toFixed(2)}s</span>`;
    const blendedPerM = (m.blended_cost * 1_000_000).toFixed(2);
    // Availability comes from configured provider keys only. Benchmark data
    // never makes a model deployable.
    const statusCell = m.deployable
      ? `<span class="pill ok">${escapeHtml(t("q.avail_yes"))}</span>`
      : `<span class="pill muted" title="${escapeHtml(t("q.avail_no_title"))}">${escapeHtml(t("q.avail_no"))}</span>`;
    const actions = m.manual_score != null
      ? `<button class="btn btn-ghost btn-sm reset-override" data-id="${escapeHtml(m.id)}" title="Revert to AA score">Reset</button>`
      : "";

    tr.innerHTML = `
      <td class="cp-col-check"><input type="checkbox" class="q-row-check" data-id="${escapeHtml(m.id)}" aria-label="${escapeHtml(tf("q.select_model", { name: m.id }))}" ${selected.has(m.id) ? "checked" : ""}></td>
      <td><code>${escapeHtml(m.id)}</code></td>
      <td>${escapeHtml(m.provider)}</td>
      <td class="num">${aaCell}</td>
      <td class="num">${manualCell}</td>
      <td class="num">${effectiveCell}</td>
      <td class="num">${tpsCell}</td>
      <td class="num">${ttftCell}</td>
      <td class="num">$${blendedPerM}</td>
      <td>${statusCell}</td>
      <td class="th-actions">${actions}</td>
    `;
    tbody.appendChild(tr);
  });

  $$(".set-override").forEach((b) =>
    b.addEventListener("click", () => openOverrideForm(b.dataset.id, b.dataset.aa))
  );
  $$(".reset-override").forEach((b) =>
    b.addEventListener("click", () => resetOverride(b.dataset.id))
  );
  $$(".q-row-check").forEach((cb) =>
    cb.addEventListener("change", () => {
      const sel = qualitySelection();
      if (cb.checked) sel.add(cb.dataset.id); else sel.delete(cb.dataset.id);
      updateQualityBulkState();
    })
  );

  const picker = qualityPicker();
  if (picker) {
    picker.setItems(rows.map((m) => ({ value: m.id, label: m.id, hint: m.provider })));
  }
  updateQualityBulkState();
}

const QUALITY_TABLE_LIMIT = 200;

function qualitySelection() {
  if (!state.qualitySelected) state.qualitySelected = new Set();
  const known = new Set((state.quality?.models || []).map((m) => m.id));
  for (const id of [...state.qualitySelected]) if (!known.has(id)) state.qualitySelected.delete(id);
  return state.qualitySelected;
}

function qualityFilteredRows() {
  const rows = state.quality?.models || [];
  const q = (state.qualityFilter || "").trim().toLowerCase();
  if (!q) return rows;
  return rows.filter((m) => m.id.toLowerCase().includes(q) || String(m.provider || "").toLowerCase().includes(q));
}

function qualityPicker() {
  const host = $("#q-ov-model-picker");
  if (!host) return null;
  if (!state.qualityPicker) {
    state.qualityPicker = new GcSelect(host, {
      multiple: true,
      allowCustom: true,
      placeholderKey: "q.ov_model_search_ph",
      onChange: (v) => { const h = $("#q-ov-model"); if (h) h.value = v.join(","); },
    });
  }
  return state.qualityPicker;
}

function updateQualityBulkState() {
  const sel = qualitySelection();
  const visible = qualityFilteredRows();
  const count = $("#q-selected-count");
  if (count) count.textContent = tf("providers.selected_count", { count: sel.size });
  const inVisible = visible.filter((m) => sel.has(m.id)).length;
  for (const box of [$("#q-select-all"), $("#q-check-all")]) {
    if (!box) continue;
    box.checked = visible.length > 0 && inVisible === visible.length;
    box.indeterminate = inVisible > 0 && inVisible < visible.length;
  }
  const none = sel.size === 0;
  for (const id of ["#q-bulk-set", "#q-bulk-clear", "#q-deselect-all"]) {
    const b = $(id);
    if (b) b.disabled = none;
  }
  const sf = $("#q-select-filtered");
  if (sf) sf.disabled = !visible.length;
}

function bindQualityBulk() {
  const bar = $("#q-bulk");
  if (!bar || bar.dataset.bound) return;
  bar.dataset.bound = "1";
  const toggleVisible = (on) => {
    const sel = qualitySelection();
    for (const m of qualityFilteredRows()) { if (on) sel.add(m.id); else sel.delete(m.id); }
    renderQualityTable();
  };
  $("#q-select-all")?.addEventListener("change", (e) => toggleVisible(e.target.checked));
  $("#q-check-all")?.addEventListener("change", (e) => toggleVisible(e.target.checked));
  $("#q-select-filtered")?.addEventListener("click", () => toggleVisible(true));
  $("#q-deselect-all")?.addEventListener("click", () => { qualitySelection().clear(); renderQualityTable(); });
  let timer = null;
  $("#q-filter")?.addEventListener("input", (e) => {
    clearTimeout(timer);
    timer = setTimeout(() => { state.qualityFilter = e.target.value; renderQualityTable(); }, 120);
  });
  $("#q-bulk-set")?.addEventListener("click", () => {
    const ids = [...qualitySelection()];
    qualityPicker()?.setValue(ids);
    const h = $("#q-ov-model");
    if (h) h.value = ids.join(",");
    const score = $("#q-ov-score");
    setQualityTab("models");
    $("#q-ov-form")?.scrollIntoView({ behavior: "smooth", block: "center" });
    score?.focus();
    if (score && score.value !== "") applyQualityOverride("set", ids);
  });
  $("#q-bulk-clear")?.addEventListener("click", () => {
    const ids = [...qualitySelection()];
    if (!ids.length) return;
    if (!confirm(tf("confirm.q_bulk_clear", { count: ids.length }))) return;
    applyQualityOverride("clear", ids);
  });
}

function renderQualityPreview() {
  const wrap = $("#quality-preview");
  const body = $("#quality-preview-body");
  if (!state.qualityPreview) {
    wrap.hidden = true;
    return;
  }
  wrap.hidden = false;
  const p = state.qualityPreview;
  if (!p.primary) {
    body.innerHTML = `<p class="muted">${escapeHtml(t("q.auto_no_provider"))}</p>`;
    return;
  }
  // primary_score is already an int 0-100 from the server (cheapest = null
  // because raw token cost has no meaningful 0-100 mapping).
  const scoreText = p.primary_score != null
    ? `<span class="pill ok">score ${p.primary_score}</span>`
    : `<span class="pill muted">unscored</span>`;
  const fbList = p.fallbacks && p.fallbacks.length
    ? `<div class="small muted">→ falls back to: ${p.fallbacks.map((f) => `<code>${escapeHtml(f)}</code>`).join(", ")}</div>`
    : "";

  // Per-axis breakdown — surfaces the same numbers the ranker used to
  // decide. Without this, `fastest` looks opaque ("primary X, score 73"
  // tells you nothing about WHY it won). Renders as
  // "tps: raw=145.0 (78/100), ttft: raw=0.41s (88/100)" etc.
  const breakdown = p.primary_score_breakdown || {};
  const breakdownEntries = Object.entries(breakdown);
  const breakdownLine = breakdownEntries.length
    ? `<div class="small muted">${breakdownEntries.map(([axis, vals]) => {
        const raw = vals && vals.raw != null
          ? `${typeof vals.raw === "number" ? vals.raw.toLocaleString(undefined, {maximumFractionDigits: 2}) : escapeHtml(String(vals.raw))}`
          : "—";
        const norm = vals && vals.normalized != null
          ? ` (${(vals.normalized * 100).toFixed(0)}/100)`
          : "";
        return `<code>${escapeHtml(axis)}</code>: ${raw}${norm}`;
      }).join(" · ")}</div>`
    : "";

  // A cost-based fallback must announce itself. Saying "scoring: quality" while
  // actually picking by price is the undisclosed proxy this page exists to
  // avoid; the backend labels it, and this surfaces the label prominently.
  const isCostProxy = /cost-as-quality|proxy|fell back/i.test(p.scoring_source || "");
  body.innerHTML = `
    <div><code>${escapeHtml(p.primary)}</code> ${scoreText}</div>
    <div class="small muted">strategy: <code>${escapeHtml(p.strategy)}</code> · scoring: ${escapeHtml(p.scoring_source)}</div>
    ${isCostProxy ? `<div class="callout callout-warn ra-proxy-warn"><p class="card-sub">This decision did <strong>not</strong> use benchmark quality. It fell back to price, which is a rough stand-in, not a measurement of model capability. Add an Artificial Analysis key or set a manual override to route on real quality.</p></div>` : ""}
    ${breakdownLine}
    ${fbList}
  `;
}

function openOverrideForm(modelId, aaHint) {
  const form = $("#q-ov-form");
  if (!form) return;
  qualityPicker()?.setValue(modelId ? [modelId] : []);
  $("#q-ov-model").value = modelId || "";
  $("#q-ov-score").value = aaHint && aaHint !== "" ? aaHint : "";
  $("#q-ov-note").value = "";
  form.scrollIntoView({ behavior: "smooth", block: "center" });
  ($("#q-ov-score") || $("#q-ov-model")).focus();
}

async function applyQualityOverride(action, explicitIds) {
  const raw = explicitIds || qualityPicker()?.getValue() || ($("#q-ov-model")?.value || "").split(/[\s,;]+/);
  const ids = [...new Set(raw.map((s) => String(s).trim()).filter(Boolean))];
  if (!ids.length) {
    toast(t("toast.q_ids_required"), "err");
    return;
  }
  if (ids.length > 500) {
    toast(t("toast.q_too_many"), "err");
    return;
  }
  const body = { model_ids: ids, action };
  if (action === "set") {
    const score = Number($("#q-ov-score")?.value);
    if (!Number.isFinite(score) || score < 0 || score > 100) {
      toast(t("toast.score_range"), "err");
      return;
    }
    body.score = score;
    const note = ($("#q-ov-note")?.value || "").trim();
    if (note) body.note = note;
  }
  try {
    const res = await api("/v1/quality/overrides/bulk", {
      method: "POST",
      body: JSON.stringify(body),
    });
    const applied = action === "clear" ? (res?.cleared ?? 0) : (res?.set ?? 0);
    toast(tf(action === "clear" ? "toast.q_bulk_clear" : "toast.q_bulk_set", { count: applied }));
    const unknown = res?.unknown_model_ids || [];
    if (unknown.length) console.warn("[quality] unknown model ids skipped:", unknown.join(", "));
    if (explicitIds) qualitySelection().clear();
    await refreshQualityPage();
  } catch (e) {
    toast(e.message, "err");
  }
}

function bindQualityOverrideForm() {
  const form = $("#q-ov-form");
  if (!form || form.dataset.bound) return;
  form.dataset.bound = "1";
  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    applyQualityOverride("set");
  });
  $("#q-ov-clear")?.addEventListener("click", () => applyQualityOverride("clear"));
  qualityPicker();
  bindQualityBulk();
}

async function resetOverride(modelId) {
  if (!confirm(tf("confirm.reset_score", {name: modelId}))) return;
  try {
    await api(`/v1/quality/overrides/${encodeURIComponent(modelId)}`, { method: "DELETE" });
    toast(tf("toast.reset", {name: modelId}), "ok");
    await refreshQualityPage();
  } catch (e) {
    toast(e.message, "err");
  }
}

function bindQualityKeyForm() {
  const form = $("#quality-key-form");
  const toggle = $("#quality-key-toggle");
  const clearBtn = $("#quality-connect-remove");
  const input = $("#quality-key-input");
  const status = $("#quality-key-status");

  if (toggle && input) {
    toggle.addEventListener("click", () => {
      input.type = input.type === "password" ? "text" : "password";
      input.focus();
    });
  }

  // Replace/Add: reveal the secure form. The previous key stays active until
  // a new one is successfully saved (PUT is atomic on commit).
  $("#quality-connect-replace")?.addEventListener("click", () => {
    if (form) {
      form.hidden = false;
      state.qaFormTouched = true;
      input?.focus();
    }
  });
  $("#quality-key-test")?.addEventListener("click", () => $("#quality-connect-test")?.click());
  $("#quality-key-cancel")?.addEventListener("click", () => {
    if (form) form.hidden = true;
    if (status) { status.textContent = ""; status.className = "auth-status"; }
  });

  // Test connection: live probe, never modifies the stored key.
  $("#quality-connect-test")?.addEventListener("click", async () => {
    const btn = $("#quality-connect-test");
    if (btn) btn.disabled = true;
    try {
      const r = await api("/v1/quality/key/test", { method: "POST" });
      const ok = r.status === "connected";
      const kind = ok ? "ok" : (r.status === "rate_limited" ? "warn" : "err");
      const label = ok ? t("qa.status.connected")
        : (r.status === "not_configured" ? t("qa.status.not_configured") : (t(`qa.err.${r.status}`) || r.status));
      toast(`${label}: ${r.detail || ""}`, kind, 6000);
      // The test result is persisted server-side; re-read the key status only.
      await loadQualityKey();
      renderQualityConnect();
      renderQualityTabIndicators();
    } catch (e) {
      toast(e.message, "err");
    } finally {
      if (btn) btn.disabled = false;
    }
  });

  if (form) {
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const value = input.value.trim();
      if (!value) return;
      const limitRaw = $("#quality-key-limit").value.trim();
      const submit = form.querySelector('button[type="submit"]');
      submit.disabled = true;
      status.textContent = t("qa.saving");
      status.className = "auth-status";
      try {
        await api("/v1/quality/key", {
          method: "PUT",
          body: JSON.stringify({
            api_key: value,
            daily_limit: limitRaw ? Number(limitRaw) : null,
          }),
        });
        input.value = "";
        form.hidden = true;
        toast(t("toast.aa_saved"), "ok");
        await refreshQualityPage();
      } catch (e) {
        status.textContent = e.message;
        status.className = "auth-status err";
      } finally {
        submit.disabled = false;
      }
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", async () => {
      if (!confirm(t("confirm.remove_aa_key"))) return;
      clearBtn.disabled = true;
      try {
        await api("/v1/quality/key", { method: "DELETE" });
        toast(t("toast.stored_removed"), "ok");
        await refreshQualityPage();
      } catch (e) {
        toast(tf("toast.remove_key_failed", {msg: e.message}), "err");
      } finally {
        clearBtn.disabled = false;
      }
    });
  }
}

function bindQualityRefresh() {
  const btn = $("#quality-refresh");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    try {
      const r = await api("/v1/quality/refresh", { method: "POST" });
      if (r?.key?.sync_status === "sync_failed") {
        const code = r.key.last_error_code;
        toast(`${t("qa.sync.sync_failed")}: ${t(`qa.err.${code}`) || code}`, code === "rate_limited" ? "warn" : "err", 6000);
      } else {
        toast(t("toast.aa_refreshed"), "ok");
      }
      await refreshQualityPage();
    } catch (e) {
      toast(tf("toast.refresh_failed", {msg: e.message}), "err");
    } finally {
      btn.disabled = false;
    }
  });
}

/* ==========================================================================
   MODELS
   ========================================================================== */
async function loadStats() {
  try {
    // One endpoint defines every count, so Overview / Providers / Routing /
    // Analytics cannot disagree about what "configured" means.
    state.stats = await api("/api/stats");
  } catch {
    state.stats = null;
  }
}

async function loadModels() {
  try {
    // /api/models, not /v1/models: the latter is the SDK-facing inference
    // route and requires an sk-geek-* key, which this dashboard deliberately
    // does not hold. Same catalog, admin-session auth.
    const data = await api("/api/models");
    state.models = data.data || [];
  } catch (e) {
    // Non-fatal — overview just shows "—".
    state.models = [];
  }
}

/* ==========================================================================
   OVERVIEW
   ========================================================================== */
function renderOverview() {
  // KPI cards
  const totalReq = (state.spend.by_model || []).reduce((a, m) => a + m.request_count, 0);
  $("#kpi-spend").textContent = fmtUsd(state.spend.total_microcents);
  $("#kpi-spend-sub").textContent = `across ${fmtNum(totalReq)} requests`;
  $("#kpi-saved").textContent = fmtUsd(state.savings.saved_microcents || 0);
  $("#kpi-saved-sub").textContent =
    state.savings.savings_percent
      ? `vs always-GPT-4o (${state.savings.savings_percent}% off)`
      : "vs always-GPT-4o baseline";

  // True p50/p99 across raw request samples — averaging per-provider
  // percentiles is the "median of medians" trap. The /v1/analytics/latency
  // endpoint only exposes pre-aggregated per-provider values, so we derive
  // global percentiles from the raw latency_ms in /v1/analytics/recent
  // (already loaded into state.recent), using the same algorithm as the
  // backend's _percentile() in app/routes/analytics.py.
  const rawLat = (state.recent || [])
    .map((r) => r.latency_ms)
    .filter((n) => Number.isFinite(n) && n >= 0);
  const p50 = percentile(rawLat, 0.5);
  const p99 = percentile(rawLat, 0.99);
  $("#kpi-p50").textContent = rawLat.length ? `${fmtNum(p50)} ms` : "— ms";
  $("#kpi-p99").textContent = rawLat.length ? `p99 ${fmtNum(p99)} ms` : "p99 — ms";

  const st = state.stats;
  const deployable = st ? st.models_deployable : null;
  const configured = st ? st.providers_configured : null;
  $("#kpi-models").textContent = deployable !== null ? fmtNum(deployable) : "—";
  $("#kpi-providers").textContent =
    configured !== null
      ? `${configured} provider${configured === 1 ? "" : "s"} configured`
      : "— providers configured";

  // Recent mini
  const mini = $("#overview-recent");
  if (!state.recent.length) {
    mini.innerHTML = `<div class="empty-mini">
      <p>${escapeHtml(t("js.ov_empty_a"))}</p>
      <p class="muted">${escapeHtml(t("js.ov_empty_b"))}</p>
    </div>`;
  } else {
    mini.innerHTML = state.recent.slice(0, 5).map((it) => {
      const ok = (it.status_code || 0) < 400;
      return `
        <div class="recent-row">
          <span class="recent-when">${fmtTime(it.created_at)}</span>
          <span class="recent-model">${escapeHtml(it.model_resolved || "—")}</span>
          <span class="recent-latency">${fmtNum(it.latency_ms)} ms</span>
          <span class="pill ${ok ? "ok" : "err"}">${ok ? "OK" : it.status_code}</span>
        </div>`;
    }).join("");
  }
}

/* ─────────────── quickstart snippet ─────────────── */
function snippetFor(lang, baseUrl, key) {
  const k = key && key.startsWith("sk-geek-") ? key : "sk-geek-...";
  if (lang === "node") {
    return `import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "${baseUrl}",
  apiKey:  "${k}",
});

const r = await client.chat.completions.create({
  model: "auto",
  messages: [{ role: "user", content: "Hello!" }],
});
console.log(r.choices[0].message.content);`;
  }
  if (lang === "curl") {
    return `curl ${baseUrl}/chat/completions \\
  -H "Authorization: Bearer ${k}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "auto",
    "messages": [{"role":"user","content":"Hello!"}]
  }'`;
  }
  return `from openai import OpenAI

client = OpenAI(
    base_url="${baseUrl}",
    api_key="${k}",
)

r = client.chat.completions.create(
    model="auto",  # or "gpt-4o-mini", "claude-3-5-sonnet-latest", ...
    messages=[{"role": "user", "content": "Hello!"}],
)
print(r.choices[0].message.content)`;
}

function currentBaseUrl() {
  // The URL the operator actually reached this console on. A reverse proxy or
  // a LAN address both work; a hardcoded localhost would be wrong for either.
  return `${location.origin}/v1`;
}

function renderEndpointControl() {
  const baseUrl = currentBaseUrl();
  let host = location.host;
  try { host = new URL(location.origin).host || host; } catch { /* keep raw */ }
  const hostEl = $("#endpoint-host");
  if (hostEl) hostEl.textContent = host;
  const full = $("#endpoint-full");
  if (full) full.textContent = baseUrl;
  const trigger = $("#endpoint-trigger");
  if (trigger) trigger.setAttribute("data-tooltip", `Endpoint: ${baseUrl}`);
}

/** Open the endpoint popover, flipping it above the trigger when there is no
 *  room below. The header is an overflow container, so this positions itself
 *  in viewport coordinates rather than relying on CSS alone. */
function toggleEndpointPop(force) {
  const pop = $("#endpoint-pop");
  const trigger = $("#endpoint-trigger");
  if (!pop || !trigger) return;
  const open = force !== undefined ? force : pop.hidden;
  if (!open) {
    pop.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
    return;
  }
  pop.hidden = false;
  trigger.setAttribute("aria-expanded", "true");
  const rect = trigger.getBoundingClientRect();
  const popRect = pop.getBoundingClientRect();
  const margin = 8;
  // Prefer below; flip above only when the popover would leave the viewport.
  let top = rect.bottom + margin;
  if (top + popRect.height > window.innerHeight - margin) {
    top = Math.max(margin, rect.top - popRect.height - margin);
  }
  // Right-align to the trigger, then clamp inside the viewport.
  let left = rect.right - popRect.width;
  left = Math.min(Math.max(margin, left), window.innerWidth - popRect.width - margin);
  pop.style.top = `${Math.round(top)}px`;
  pop.style.left = `${Math.round(left)}px`;
  pop.style.position = "fixed";
}

function renderQuickstart() {
  const baseUrl = currentBaseUrl();
  renderEndpointControl();
  $("#help-base-url").textContent = baseUrl;
  // The snippet shows a placeholder, never a real key: the dashboard does not
  // hold one. Operators copy their own key from Settings -> API Keys.
  $("#quickstart-code").textContent = snippetFor(state.lang, baseUrl, null);
}

function bindQuickstart() {
  $$("#lang-seg .seg-btn").forEach((b) =>
    b.addEventListener("click", () => {
      $$("#lang-seg .seg-btn").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      state.lang = b.dataset.lang;
      renderQuickstart();
    })
  );
  $("#copy-snippet").addEventListener("click", (e) => {
    copyToClipboard($("#quickstart-code").textContent, e.currentTarget);
  });
  $("#endpoint-copy")?.addEventListener("click", () => {
    copyToClipboard(currentBaseUrl());
  });
  $("#endpoint-pop-copy")?.addEventListener("click", () => {
    copyToClipboard(currentBaseUrl());
    toggleEndpointPop(false);
  });
  $("#endpoint-trigger")?.addEventListener("click", (e) => {
    e.stopPropagation();
    toggleEndpointPop();
  });
  // Close on outside click, Escape, or scroll/resize (position would go stale).
  document.addEventListener("click", (e) => {
    const ctl = $("#endpoint-ctl");
    if (ctl && !ctl.contains(e.target)) toggleEndpointPop(false);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") toggleEndpointPop(false);
  });
  window.addEventListener("resize", () => toggleEndpointPop(false));
  window.addEventListener("scroll", () => toggleEndpointPop(false), true);
}

/* ─────────────── onboarding checklist ─────────────── */
function syncOnboarding() {
  const banner = $("#getting-started");
  if (!banner) return;
  if (localStorage.getItem(ONBOARDING_KEY) === "1") {
    banner.classList.add("dismissed");
    return;
  }
  // A working custom provider is a configured provider. Counting only built-in
  // keys left "Add at least one provider key" permanently unticked for anyone
  // running entirely on custom providers.
  const step1 = state.stats ? state.stats.providers_configured > 0 : state.providers.length > 0;
  const step2 = !!state.routing.strategy;
  const step3 = state.recent.length > 0;
  $("#step-1").classList.toggle("done", step1);
  $("#step-2").classList.toggle("done", step2);
  $("#step-3").classList.toggle("done", step3);
  if (step1 && step2 && step3) {
    setTimeout(() => {
      banner.classList.add("dismissed");
      localStorage.setItem(ONBOARDING_KEY, "1");
    }, 1800);
  }
}

function bindOnboarding() {
  $("#dismiss-getting-started").addEventListener("click", () => {
    localStorage.setItem(ONBOARDING_KEY, "1");
    $("#getting-started").classList.add("dismissed");
  });
}

/* ==========================================================================
   HEALTH POLLING
   ========================================================================== */
async function pollHealth() {
  const dot = $("#health-dot");
  const txt = $("#health-text");
  async function tick() {
    try {
      await api("/health");
      dot.classList.remove("err"); dot.classList.add("ok");
      txt.textContent = t("status.connected");
    } catch {
      dot.classList.remove("ok"); dot.classList.add("err");
      txt.textContent = t("status.disconnected");
    }
  }
  await tick();
  setInterval(tick, 15_000);
}

/* ==========================================================================
   HELP DRAWER
   ========================================================================== */
function openHelp() {
  $("#help-drawer").hidden = false;
  $("#scrim").hidden = false;
}
function closeHelp() {
  const d = $("#help-drawer");
  d.hidden = true;
  $("#scrim").hidden = true;
}
function bindHelp() {
  $("#open-help").addEventListener("click", openHelp);
  $("#close-help").addEventListener("click", closeHelp);
  $("#scrim").addEventListener("click", () => {
    closeHelp();
  });
}

/* ==========================================================================
   COMMAND PALETTE
   ========================================================================== */
function paletteCommands() {
  return [
    { id: "go-overview",  title: "Go to Overview",       meta: "Tab",  hint: "1",  do: () => setTab("overview")  },
    { id: "go-providers", title: "Go to Providers",      meta: "Tab",  hint: "2",  do: () => setTab("providers") },
    { id: "go-routing",   title: "Go to Routing",        meta: "Tab",  hint: "3",  do: () => setTab("routing")   },
    { id: "go-analytics", title: "Go to Analytics",      meta: "Tab",  hint: "4",  do: () => setTab("analytics") },
    { id: "go-keys",      title: "Go to API keys",       meta: "Tab",  hint: "5",  do: () => setTab("keys")      },
    { id: "copy-base",    title: "Copy base URL",        meta: "Action", hint: "", do: () => copyToClipboard(`${location.origin}/v1`) },
    { id: "copy-snip",    title: "Copy quickstart snippet", meta: "Action", hint: "", do: () => copyToClipboard($("#quickstart-code").textContent) },
    { id: "open-help",    title: "Open help & docs",     meta: "Help", hint: "?",  do: () => openHelp() },
    { id: "toggle-theme", title: "Toggle light / dark theme", meta: "Action", hint: "", do: () => cycleTheme() },
    { id: "logout",       title: "Sign out (forget API key)", meta: "Action", hint: "", do: () => logout() },
  ];
}

let paletteFocus = 0;

function openPalette() {
  $("#palette").hidden = false;
  $("#palette-input").value = "";
  paletteFocus = 0;
  renderPalette("");
  setTimeout(() => $("#palette-input").focus(), 10);
}
function closePalette() { $("#palette").hidden = true; }

function renderPalette(query) {
  const q = query.trim().toLowerCase();
  const all = paletteCommands();
  const items = q ? all.filter((c) => c.title.toLowerCase().includes(q)) : all;
  const list = $("#palette-list");
  if (!items.length) {
    list.innerHTML = `<li class="palette-empty">No matches</li>`;
    return;
  }
  list.innerHTML = items.map((c, i) => `
    <li class="palette-item ${i === paletteFocus ? "focused" : ""}" data-id="${c.id}">
      <span>${escapeHtml(c.title)}</span>
      <span class="meta">${escapeHtml(c.hint || c.meta)}</span>
    </li>
  `).join("");
  $$("#palette-list .palette-item").forEach((el) =>
    el.addEventListener("click", () => {
      const cmd = items.find((c) => c.id === el.dataset.id);
      if (cmd) { closePalette(); cmd.do(); }
    })
  );
}

function bindPalette() {
  $("#open-palette").addEventListener("click", openPalette);
  $("#palette-close").addEventListener("click", closePalette);
  const input = $("#palette-input");
  input.addEventListener("input", () => { paletteFocus = 0; renderPalette(input.value); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      closePalette();
      return;
    }
    const visible = $$("#palette-list .palette-item");
    if (e.key === "ArrowDown") {
      e.preventDefault();
      paletteFocus = Math.min(visible.length - 1, paletteFocus + 1);
      renderPalette(input.value);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      paletteFocus = Math.max(0, paletteFocus - 1);
      renderPalette(input.value);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const focused = visible[paletteFocus];
      if (focused) {
        const all = paletteCommands();
        const q = input.value.trim().toLowerCase();
        const items = q ? all.filter((c) => c.title.toLowerCase().includes(q)) : all;
        const cmd = items.find((c) => c.id === focused.dataset.id);
        if (cmd) { closePalette(); cmd.do(); }
      }
    }
  });
  // click on the backdrop (anywhere outside the card) closes
  $("#palette").addEventListener("click", (e) => {
    if (!e.target.closest(".palette-card")) closePalette();
  });
}

/* ==========================================================================
   GLOBAL KEYBOARD SHORTCUTS
   ========================================================================== */
function bindKeyboard() {
  document.addEventListener("keydown", (e) => {
    const inField = e.target.matches("input, textarea, [contenteditable=true]");
    const cmdK = (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k";

    if (cmdK) {
      e.preventDefault();
      if ($("#palette").hidden) openPalette(); else closePalette();
      return;
    }
    if (e.key === "Escape") {
      if (!$("#palette").hidden) closePalette();
      else if (!$("#help-drawer").hidden) closeHelp();
      return;
    }
    if (inField) return;
    if ($("#auth-gate").hidden === false) return;

    if (e.key === "?") { e.preventDefault(); $("#help-drawer").hidden ? openHelp() : closeHelp(); }
    if (e.key >= "1" && e.key <= "9" && !e.altKey && !e.ctrlKey && !e.metaKey) {
      // The sidebar's own `data-shortcut` attribute is the single source of
      // truth, so the <kbd> hint a user reads and the key that is handled can
      // never drift apart. Items without one (Chat, Local AI, Model data)
      // show no number and have no digit shortcut.
      const target = $(`#tabs .nav-item[data-shortcut="${e.key}"]`);
      if (target) setTab(target.dataset.tab);
    }
  });
}

/** ⌘ on Apple platforms, Ctrl elsewhere — the hint matches the key the
 *  handler above actually accepts (metaKey || ctrlKey). */
function applyModifierKeyLabels() {
  const platform = navigator.userAgentData?.platform || navigator.platform || "";
  if (!/mac|iphone|ipad/i.test(platform)) return;
  $$(".mod-key").forEach((el) => { el.textContent = "⌘"; });
  $$(".mod-key-combo").forEach((el) => { el.textContent = "⌘K"; });
  const btn = $("#open-palette");
  if (btn) btn.title = "Command palette (⌘K)";
}

/* ==========================================================================
   BOOT
   ========================================================================== */
document.addEventListener("DOMContentLoaded", async () => {
  state.locale = detectLocale();
  // Purge any API key an older dashboard left in localStorage. It is no longer
  // a credential for this UI, and leaving a live sk-geek-* secret in browser
  // storage is exactly the exposure this release removes.
  try { localStorage.removeItem(LEGACY_KEY_STORAGE); } catch { /* private mode */ }
  applyI18n();
  bindTheme();
  bindLocalePicker();
  bindAuth();
  bindTabs();
  bindProviderForm();
  bindCustomProviderToggle();
  bindLegacyCustomBanner();
  bindRouting();
  bindLocalConnect();
  bindProfiles();
  bindBaseline();
  bindIntegrations();
  bindIntelligence();
  bindWindowSeg();
  bindKeyForm();
  bindSecurity();
  bindQualityTabs();
  bindQualityKeyForm();
  bindQualityOverrideForm();
  bindQualityRefresh();
  bindHelp();
  bindPalette();
  bindKeyboard();
  applyModifierKeyLabels();
  bindQuickstart();
  bindOnboarding();

  // Decide which auth screen to show, or go straight to the dashboard when a
  // valid session cookie is already present.
  await bootAuth();
});

window.addEventListener("hashchange", () => {
  const t = (location.hash || "").replace("#", "");
  if (TAB_META[t]) setTab(t);
});

/* ==========================================================================
   ROUTING PROFILES
   ========================================================================== */
const PROFILE_TEMPLATES = {
  // Strategy + a description only. No commercial model names are baked in:
  // the admin picks models from what is actually registered here.
  economy: { display_name: "Economy", strategy: "cheapest", description: "Minimise spend." },
  premium: { display_name: "Premium", strategy: "quality", description: "Prioritise the strongest models." },
  coding: { display_name: "Coding", strategy: "adaptive_gated", description: "Software development; tool calls go to the Hard pool." },
  fast: { display_name: "Fast", strategy: "balanced", description: "Favour low latency." },
};
const STRATEGY_TIER = {
  balanced: "tier-balanced", cheapest: "tier-mundane", quality: "tier-hard",
  adaptive: "tier-adaptive", adaptive_gated: "tier-frontier", fastest: "tier-fallback",
};

state.profiles = [];
state.profileQuery = "";
state.profileEditing = null;      // profile being edited (null = create)
state.profileModels = { total: 0, models: [] };
state.profileModelQuery = "";
state.pfDraft = null;             // {allowed:Set, mundane:Set, hard:Set, fallback:Set}

async function loadProfiles() {
  try {
    const data = await api("/v1/routing-profiles");
    state.profiles = data.profiles || [];
  } catch (e) {
    state.profiles = [];
    toast(tf("toast.load_profiles_failed", {msg: e.message}), "err");
  }
}

function _timeAgo(iso) {
  if (!iso) return "never";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "never";
  const s = Math.max(0, (Date.now() - d.getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function renderProfiles() {
  const list = $("#profile-list");
  if (!list) return;
  const q = state.profileQuery.trim().toLowerCase();
  const rows = state.profiles.filter((p) =>
    !q || p.display_name.toLowerCase().includes(q) || p.slug.includes(q));
  const custom = state.profiles.filter((p) => !p.is_builtin);
  $("#profile-empty").hidden = custom.length > 0 || !!q;
  if (!rows.length) {
    list.innerHTML = q ? `<p class="muted small">No profile matches “${escapeHtml(q)}”.</p>` : "";
    return;
  }
  const anyDefault = state.profiles.some((p) => p.is_default);
  list.innerHTML = rows.map((p) => {
    const tier = STRATEGY_TIER[p.strategy] || "tier-inactive";
    const ext = p.profile || {};
    const restrictions = [];
    if ((ext.models || []).length) restrictions.push(`${ext.models.length} allowed model${ext.models.length === 1 ? "" : "s"}`);
    if ((ext.providers || []).length) restrictions.push(`${ext.providers.length} provider${ext.providers.length === 1 ? "" : "s"}`);
    if (ext.max_cost_per_million_micros != null) restrictions.push(`≤ $${(ext.max_cost_per_million_micros / 1e6).toFixed(2)}/1M`);
    const isDefault = p.is_default || (p.is_builtin && !anyDefault);
    return `
    <div class="profile-row ${p.is_enabled ? "" : "is-off"}" role="listitem" data-profile-id="${escapeHtml(p.id)}">
      <span class="profile-dot ${p.is_enabled ? tier : "tier-inactive"}" aria-hidden="true"></span>
      <div class="profile-main">
        <div class="profile-name">
          <strong>${escapeHtml(p.display_name)}</strong>
          <code class="profile-slug">${escapeHtml(p.slug)}</code>
          ${isDefault ? '<span class="status-chip avail-pinned_only">Default</span>' : ""}
          ${p.is_builtin ? '<span class="proto-badge">Built-in</span>' : ""}
          ${p.is_enabled ? "" : '<span class="status-chip avail-not_deployable">Disabled</span>'}
        </div>
        <div class="profile-meta">
          <span class="tier-chip ${tier}">${escapeHtml(p.strategy_label || p.strategy)}</span>
          ${restrictions.length ? `<span>${escapeHtml(restrictions.join(" · "))}</span>` : '<span class="muted">Any Auto-eligible model</span>'}
        </div>
      </div>
      <div class="profile-usage">
        <span class="profile-usage-n">${fmtNum(p.requests_30d || 0)}</span>
        <span class="muted small">req · 30d</span>
        <span class="muted small">used ${escapeHtml(_timeAgo(p.last_used_at))}</span>
      </div>
      <details class="cp-menu">
        <summary class="btn btn-ghost btn-sm" aria-label="Actions for ${escapeHtml(p.display_name)}">Actions</summary>
        <div class="cp-menu-items">
          ${p.is_builtin
            ? `<button type="button" class="cp-menu-item" data-go-tab="routing">Edit on Routing page</button>`
            : `<button type="button" class="cp-menu-item" data-pa="edit">Edit</button>`}
          <button type="button" class="cp-menu-item" data-pa="duplicate">Duplicate</button>
          <button type="button" class="cp-menu-item" data-pa="connect">Connect to app</button>
          ${isDefault ? "" : `<button type="button" class="cp-menu-item" data-pa="default">Set as default</button>`}
          <button type="button" class="cp-menu-item" data-pa="export">Export JSON</button>
          ${p.is_builtin ? "" : `<button type="button" class="cp-menu-item" data-pa="toggle">${p.is_enabled ? "Disable" : "Enable"}</button>`}
          ${p.is_builtin ? "" : `<button type="button" class="cp-menu-item danger" data-pa="delete">Delete…</button>`}
        </div>
      </details>
    </div>`;
  }).join("");
}

function _profileById(id) { return state.profiles.find((p) => p.id === id); }

function _downloadJson(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2) + "\n"], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
}

async function exportProfile(p) {
  try {
    const data = await api(`/v1/routing-profiles/${encodeURIComponent(p.id)}/export`);
    _downloadJson(`geekcubo-profile-${p.slug}.json`, data);
  } catch (e) { toast(e.message, "err"); }
}

async function profileAction(action, p) {
  try {
    if (action === "edit") return openProfileEditor(p);
    if (action === "connect") {
      state.intPreselect = p.slug;
      return setTab("integrations");
    }
    if (action === "export") return exportProfile(p);
    if (action === "duplicate") {
      await api(`/v1/routing-profiles/${encodeURIComponent(p.id)}/duplicate`, { method: "POST", body: "{}" });
      toast(tf("toast.duplicated", {name: p.display_name}), "ok");
    } else if (action === "default") {
      await api(`/v1/routing-profiles/${encodeURIComponent(p.id)}/default`, { method: "POST", body: "{}" });
      toast(tf("toast.now_default", {name: p.display_name}), "ok");
    } else if (action === "toggle") {
      await api(`/v1/routing-profiles/${encodeURIComponent(p.id)}`, {
        method: "PUT", body: JSON.stringify({ is_enabled: !p.is_enabled }),
      });
    } else if (action === "delete") {
      return openDeleteProfile(p);
    }
    await loadProfiles();
    renderProfiles();
  } catch (e) { toast(e.message, "err"); }
}

function openDeleteProfile(p) {
  const dlg = $("#profile-delete-dialog");
  $("#pd-body").innerHTML =
    `<strong>${escapeHtml(p.display_name)}</strong> (<code>${escapeHtml(p.slug)}</code>) will be removed. ` +
    `Clients still sending <code>model: "${escapeHtml(p.slug)}"</code> will get an error.`;
  $("#pd-default").hidden = !p.is_default;
  $("#pd-export").onclick = () => exportProfile(p);
  $("#pd-confirm").onclick = async () => {
    try {
      const r = await api(`/v1/routing-profiles/${encodeURIComponent(p.id)}`, { method: "DELETE" });
      dlg.close();
      toast(tf("toast.deleted", {name: p.display_name}) + (r.default_reassigned_to ? t("toast.default_reassigned") : ""), "ok");
      await loadProfiles();
      renderProfiles();
    } catch (e) { toast(e.message, "err"); }
  };
  dlg.showModal();
}

/* ─── editor ─── */
async function _loadProfileModels() {
  const q = encodeURIComponent(state.profileModelQuery.trim());
  try {
    state.profileModels = await api(`/api/routing/models?scope=routable&q=${q}&limit=60&offset=0`);
  } catch (e) {
    state.profileModels = { total: 0, models: [] };
  }
}

function _renderProfileModelRows() {
  const tbody = $("#pf-model-rows");
  const d = state.pfDraft;
  const data = state.profileModels;
  $("#pf-model-count").textContent = data.total > data.models.length
    ? `showing ${data.models.length} of ${data.total}` : `${data.total} models`;
  if (!data.models.length) {
    tbody.innerHTML = `<tr><td colspan="3" class="muted small">No deployable models match. Add models under <a href="#" data-go-tab="providers">Providers</a>.</td></tr>`;
    return;
  }
  const cols = [["allowed", "Allow", "tier-adaptive"], ["mundane", "Mundane", "tier-mundane"],
                ["hard", "Hard", "tier-hard"], ["fallback", "Fallback", "tier-fallback"]];
  tbody.innerHTML = data.models.map((m) => {
    const price = m.input_per_million == null && m.output_per_million == null
      ? '<span class="muted">unknown</span>'
      : `$${((m.input_per_million || 0) + (m.output_per_million || 0)).toFixed(2)}`;
    const btns = cols.map(([key, label, tier]) => {
      const on = d[key].has(m.id);
      return `<button type="button" class="pool-toggle ${tier}${on ? " on" : ""}" data-pf-toggle="${key}" data-model="${escapeHtml(m.id)}" aria-pressed="${on}">${label}</button>`;
    }).join("");
    return `<tr><td><code>${escapeHtml(m.id)}</code></td><td>${price}</td><td class="th-actions"><div class="pool-toggles">${btns}</div></td></tr>`;
  }).join("");
  // Preferred-model dropdown follows the allowed set (or everything).
  const sel = $("#pf-preferred");
  const keep = sel.value;
  const options = d.allowed.size ? [...d.allowed] : data.models.map((m) => m.id);
  sel.innerHTML = '<option value="">None — let the strategy decide</option>' +
    options.map((id) => `<option value="${escapeHtml(id)}">${escapeHtml(id)}</option>`).join("");
  if (keep && options.includes(keep)) sel.value = keep;
}

async function openProfileEditor(p, template) {
  state.profileEditing = p || null;
  const src = p || { ...(template || {}), policy: null, profile: {} };
  const policy = src.policy || {};
  const ext = src.profile || {};
  state.pfDraft = {
    allowed: new Set(ext.models || []),
    mundane: new Set(policy.pools?.mundane || []),
    hard: new Set(policy.pools?.hard || []),
    fallback: new Set(policy.pools?.fallback || []),
  };
  $("#profile-dialog-title").textContent = p ? `Edit ${p.display_name}` : "New profile";
  $("#pf-name").value = src.display_name || "";
  $("#pf-slug").value = src.slug || "";
  $("#pf-slug").dataset.touched = p ? "1" : "";
  $("#pf-slug-help").innerHTML = p
    ? `Changing this breaks clients sending <code>${escapeHtml(p.slug)}</code>. You will be asked to confirm.`
    : 'Clients send this as <code>model</code>. Lowercase letters, digits, hyphens.';
  $("#pf-desc").value = src.description || "";
  $("#pf-strategy").value = src.strategy || "balanced";
  $("#pf-maxcost").value = ext.max_cost_per_million_micros != null ? (ext.max_cost_per_million_micros / 1e6) : "";
  $("#pf-timeout").value = ext.timeout_seconds || "";
  $("#pf-fallback").checked = policy.fallback ? policy.fallback.enabled !== false : true;
  // Spec default for new profiles: 3 total attempts.
  $("#pf-attempts").value = policy.fallback?.max_attempts ?? 3;
  $("#pf-enabled").checked = src.is_enabled !== false;
  $("#pf-error").hidden = true;
  state.profileModelQuery = "";
  $("#pf-model-search").value = "";
  await _loadProfileModels();
  _renderProfileModelRows();
  if (ext.preferred_model) $("#pf-preferred").value = ext.preferred_model;
  $("#profile-dialog").showModal();
  $("#pf-name").focus();
}

function _slugify(name) {
  return (name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 64);
}

async function saveProfile(e) {
  e.preventDefault();
  const errEl = $("#pf-error");
  const fail = (msg) => { errEl.textContent = msg; errEl.hidden = false; };
  const name = $("#pf-name").value.trim();
  if (!name) return fail("Name is required.");
  const slug = $("#pf-slug").value.trim();
  const d = state.pfDraft;
  const maxcost = $("#pf-maxcost").value.trim();
  const timeout = $("#pf-timeout").value.trim();
  const attempts = parseInt($("#pf-attempts").value, 10);
  const editing = state.profileEditing;
  const basePolicy = editing?.policy ? JSON.parse(JSON.stringify(editing.policy)) : {};
  delete basePolicy.profile;
  const policy = {
    ...basePolicy,
    pools: { mundane: [...d.mundane], hard: [...d.hard], fallback: [...d.fallback] },
    fallback: {
      ...(basePolicy.fallback || {}),
      enabled: $("#pf-fallback").checked,
      max_attempts: Number.isFinite(attempts) ? attempts : 3,
    },
  };
  const profile = {
    models: [...d.allowed],
    providers: editing?.profile?.providers || [],
    max_cost_per_million_micros: maxcost === "" ? null : Math.round(parseFloat(maxcost) * 1e6),
    timeout_seconds: timeout === "" ? null : parseInt(timeout, 10),
    preferred_model: $("#pf-preferred").value || null,
  };
  const body = {
    display_name: name,
    description: $("#pf-desc").value.trim(),
    strategy: $("#pf-strategy").value,
    is_enabled: $("#pf-enabled").checked,
    policy, profile,
  };
  try {
    if (editing) {
      if (slug && slug !== editing.slug) {
        if (!confirm(tf("confirm.change_slug", {old: editing.slug, new: slug}))) return;
        body.slug = slug;
        body.confirm_slug_change = true;
      }
      await api(`/v1/routing-profiles/${encodeURIComponent(editing.id)}`, { method: "PUT", body: JSON.stringify(body) });
    } else {
      if (slug) body.slug = slug;
      await api("/v1/routing-profiles", { method: "POST", body: JSON.stringify(body) });
    }
    $("#profile-dialog").close();
    toast(tf("toast.saved_profile", {name}), "ok");
    await loadProfiles();
    renderProfiles();
  } catch (err) {
    fail(err.message);
  }
}

let _pfSearchTimer = null;
function bindProfiles() {
  if (!$("#panel-profiles")) return;
  $("#profile-search").addEventListener("input", (e) => {
    state.profileQuery = e.target.value;
    renderProfiles();
  });
  $("#profile-new-btn").addEventListener("click", () => openProfileEditor(null));
  $$("[data-profile-template]").forEach((b) =>
    b.addEventListener("click", () => openProfileEditor(null, PROFILE_TEMPLATES[b.dataset.profileTemplate])));
  $("#profile-list").addEventListener("click", (e) => {
    const item = e.target.closest("[data-pa]");
    if (!item) return;
    const row = item.closest("[data-profile-id]");
    const p = _profileById(row.dataset.profileId);
    item.closest("details")?.removeAttribute("open");
    if (p) profileAction(item.dataset.pa, p);
  });
  // Import
  $("#profile-import-btn").addEventListener("click", () => $("#profile-import-file").click());
  $("#profile-import-file").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > 256 * 1024) return toast(t("toast.file_too_large"), "err");
    try {
      const data = JSON.parse(await file.text());
      const r = await api("/v1/routing-profiles/import", { method: "POST", body: JSON.stringify(data) });
      const unknown = r.unknown_models || [];
      toast(unknown.length
        ? `Imported ${r.display_name}. ${unknown.length} model(s) not registered here: ${unknown.join(", ")}`
        : `Imported ${r.display_name}`, unknown.length ? "err" : "ok");
      await loadProfiles();
      renderProfiles();
    } catch (err) {
      toast(err instanceof SyntaxError ? "That file is not valid JSON." : err.message, "err");
    }
  });
  // Editor
  $("#profile-form").addEventListener("submit", saveProfile);
  $("#pf-name").addEventListener("input", () => {
    if (!$("#pf-slug").dataset.touched) $("#pf-slug").value = _slugify($("#pf-name").value);
  });
  $("#pf-slug").addEventListener("input", () => { $("#pf-slug").dataset.touched = "1"; });
  $("#pf-model-search").addEventListener("input", (e) => {
    clearTimeout(_pfSearchTimer);
    _pfSearchTimer = setTimeout(async () => {
      state.profileModelQuery = e.target.value;
      await _loadProfileModels();
      _renderProfileModelRows();
    }, 200);
  });
  $("#pf-model-rows").addEventListener("click", (e) => {
    const b = e.target.closest("[data-pf-toggle]");
    if (!b) return;
    const set = state.pfDraft[b.dataset.pfToggle];
    const id = b.dataset.model;
    if (set.has(id)) set.delete(id); else set.add(id);
    _renderProfileModelRows();
  });
  // Generic close buttons for every <dialog>.
  $$("[data-dialog-close]").forEach((b) =>
    b.addEventListener("click", () => b.closest("dialog")?.close()));
}

/* ==========================================================================
   INTEGRATIONS — "Connect a tool"
   ========================================================================== */
state.intOptions = null;
state.intApp = "opencode";
state.intVariant = null;
state.intResult = null;
state.intPreselect = null;

async function loadIntegrationData() {
  try {
    state.intOptions = await api("/api/integrations/options");
  } catch (e) {
    state.intOptions = null;
    toast(tf("toast.load_integrations_failed", {msg: e.message}), "err");
  }
}

function _intBaseUrl() {
  const remote = $('input[name="int-ep"][value="remote"]').checked;
  if (remote) return ($("#int-remote-url").value.trim() || state.intOptions?.default_remote_base_url || "");
  return state.intOptions?.local_base_url || `${location.origin}/v1`;
}

function renderIntegrationApps() {
  const q = ($("#int-search").value || "").trim().toLowerCase();
  const apps = (state.intOptions?.apps || []).filter((a) => !q || a.label.toLowerCase().includes(q));
  $("#int-apps").innerHTML = apps.map((a) => {
    const on = a.id === state.intApp;
    const badge = a.supported === "partial"
      ? '<span class="status-chip avail-unpriced">Partial</span>'
      : a.supported === false ? '<span class="status-chip avail-not_deployable">Unsupported</span>' : "";
    return `<button type="button" class="int-app${on ? " on" : ""}" role="radio" aria-checked="${on}" data-int-app="${escapeHtml(a.id)}">
      <span class="int-app-name">${escapeHtml(a.label)} ${badge}</span>
      ${a.note ? `<span class="int-app-note">${escapeHtml(a.note)}</span>` : ""}
    </button>`;
  }).join("") || '<p class="muted small">No tool matches.</p>';
}

function renderIntegrations() {
  if (!state.intOptions) return;
  renderIntegrationApps();
  const sel = $("#int-model");
  const keep = state.intPreselect || sel.value || "auto";
  const routing = state.intOptions.routing_ids || [];
  const models = state.intOptions.models || [];
  sel.innerHTML =
    `<optgroup label="Routing">${routing.map((r) => `<option value="${escapeHtml(r.id)}">${escapeHtml(r.label)}</option>`).join("")}</optgroup>` +
    (models.length ? `<optgroup label="Pinned model">${models.map((m) => `<option value="${escapeHtml(m)}">${escapeHtml(m)}</option>`).join("")}</optgroup>` : "");
  const allIds = routing.map((r) => r.id).concat(models);
  sel.value = allIds.includes(keep) ? keep : "auto";
  state.intPreselect = null;
  refreshIntegrationConfig();
}

async function refreshIntegrationConfig() {
  const base = _intBaseUrl();
  const params = new URLSearchParams({ app: state.intApp, model: $("#int-model").value || "auto", base_url: base });
  if (state.intVariant) params.set("variant", state.intVariant);
  try {
    const r = await api(`/api/integrations/config?${params}`);
    state.intResult = r;
    $("#int-status").innerHTML = "";
    $("#int-filename").textContent = r.filename;
    $("#int-code").textContent = r.code;
    $("#int-code").dataset.lang = r.language;
    $("#int-download").hidden = !r.downloadable;
    const vw = $("#int-variant-wrap");
    vw.hidden = !(r.variants && r.variants.length);
    if (r.variants && r.variants.length) {
      $("#int-variant").innerHTML = r.variants.map((v) =>
        `<option value="${escapeHtml(v.id)}"${v.id === r.variant ? " selected" : ""}>${escapeHtml(v.label)}</option>`).join("");
    }
    // Steps may contain inline `code` and occasionally a JSON block.
    const md = (txt) => escapeHtml(txt).replace(/`([^`]+)`/g, "<code>$1</code>");
    $("#int-steps").innerHTML = (r.steps || []).map((st) =>
      st.trim().startsWith("{") ? `<li><pre class="int-code int-code-sm">${escapeHtml(st)}</pre></li>` : `<li>${md(st)}</li>`).join("");
    const notes = (r.notes || []).map((n) => `<li>${md(n)}</li>`).join("");
    const warns = (r.warnings || []).map((w) => `<li>${md(w)}</li>`).join("");
    $("#int-notes").innerHTML =
      (warns ? `<div class="routing-warnings-box"><strong>Limits</strong><ul>${warns}</ul></div>` : "") +
      (notes ? `<ul class="int-note-list">${notes}</ul>` : "") +
      (r.docs ? `<p class="small"><a href="${escapeHtml(r.docs)}" target="_blank" rel="noopener noreferrer">Official ${escapeHtml(r.label)} documentation ↗</a></p>` : "");
  } catch (e) {
    $("#int-status").innerHTML = `<div class="routing-warnings-box">${escapeHtml(e.message)}</div>`;
    $("#int-code").textContent = "";
  }
}

let _intUrlTimer = null;
function bindIntegrations() {
  if (!$("#panel-integrations")) return;
  $("#int-search").addEventListener("input", renderIntegrationApps);
  $("#int-apps").addEventListener("click", (e) => {
    const b = e.target.closest("[data-int-app]");
    if (!b) return;
    state.intApp = b.dataset.intApp;
    state.intVariant = null;
    renderIntegrationApps();
    refreshIntegrationConfig();
  });
  $("#int-model").addEventListener("change", refreshIntegrationConfig);
  $("#int-variant").addEventListener("change", (e) => { state.intVariant = e.target.value; refreshIntegrationConfig(); });
  $$('input[name="int-ep"]').forEach((r) => r.addEventListener("change", () => {
    $("#int-remote-url").hidden = !$('input[name="int-ep"][value="remote"]').checked;
    refreshIntegrationConfig();
  }));
  $("#int-remote-url").addEventListener("input", () => {
    clearTimeout(_intUrlTimer);
    _intUrlTimer = setTimeout(refreshIntegrationConfig, 300);
  });
  $("#int-copy").addEventListener("click", () => {
    if (state.intResult) copyToClipboard(state.intResult.code);
  });
  $("#int-download").addEventListener("click", () => {
    const r = state.intResult;
    if (!r || !r.downloadable) return;
    const blob = new Blob([r.code], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = r.filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  });
}

/* placeholder until Model Intelligence ships below */

/* ==========================================================================
   MODEL INTELLIGENCE
   ========================================================================== */
state.qualityKey = null;
state.miSources = [];
state.miLookup = null;

async function loadIntelligence() {
  try {
    const data = await api("/v1/model-intelligence/sources");
    state.miSources = data.sources || [];
  } catch (e) {
state.qualityKey = null;
state.qaFormTouched = false;
state.miSources = [];
    toast(tf("toast.load_mi_failed", {msg: e.message}), "err");
  }
}

function _fmtWhen(iso) {
  if (!iso) return "never";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "never";
  return d.toLocaleString();
}

function renderIntelligence() {
  const list = $("#mi-list");
  if (!list) return;
  if (!state.miSources.length) {
    list.innerHTML = '<p class="muted small">No sources configured.</p>';
    return;
  }
  list.innerHTML = state.miSources.map((s) => `
    <div class="mi-row ${s.is_enabled ? "" : "is-off"}" data-mi-id="${escapeHtml(s.id)}">
      <div class="mi-main">
        <div class="mi-name">
          <strong>${escapeHtml(s.name)}</strong>
          ${s.is_builtin ? '<span class="proto-badge">Built-in</span>' : ""}
          <span class="status-chip ${s.is_enabled ? "avail-auto" : "avail-not_deployable"}">${s.is_enabled ? "Enabled" : "Disabled"}</span>
          ${s.last_error ? `<span class="status-chip avail-unpriced" title="${escapeHtml(s.last_error)}">Error</span>` : ""}
          ${s.is_enabled && s.stale ? '<span class="status-chip avail-pinned_only">Stale</span>' : ""}
        </div>
        <div class="mi-meta">
          <span class="muted small">Priority ${s.priority}</span>
          <span class="muted small">${s.entry_count ? fmtNum(s.entry_count) + " models cached" : "no data yet"}</span>
          <span class="muted small">last success: ${escapeHtml(_fmtWhen(s.last_success_at))}</span>
          <span class="muted small">last attempt: ${escapeHtml(_fmtWhen(s.last_attempt_at))}</span>
          ${s.has_token ? '<span class="muted small">token stored</span>' : ""}
        </div>
        ${s.description ? `<p class="muted small mi-desc">${escapeHtml(s.description)}</p>` : ""}
        ${s.last_error ? `<p class="mi-error-line">${escapeHtml(s.last_error)}</p>` : ""}
      </div>
      <div class="mi-actions">
        <button type="button" class="btn btn-ghost btn-sm" data-mi-test="${escapeHtml(s.id)}">Test</button>
        <button type="button" class="btn btn-ghost btn-sm" data-mi-refresh="${escapeHtml(s.id)}">Refresh</button>
        <button type="button" class="btn btn-ghost btn-sm" data-mi-toggle="${escapeHtml(s.id)}" data-on="${s.is_enabled}">${s.is_enabled ? "Disable" : "Enable"}</button>
        ${s.is_builtin ? "" : `<button type="button" class="btn btn-ghost btn-sm btn-danger" data-mi-delete="${escapeHtml(s.id)}">Delete</button>`}
      </div>
    </div>`).join("");
}

function renderMiLookup(r) {
  const out = $("#mi-lookup-result");
  if (!r) { out.innerHTML = ""; return; }
  const field = (label, f) => {
    const v = r.fields?.[f];
    if (!v || v.value == null) {
      return `<tr><td>${label}</td><td class="muted">unknown</td><td class="muted">—</td><td></td></tr>`;
    }
    const shown = f.endsWith("_per_million") ? `$${Number(v.value).toFixed(4)} / 1M`
      : f === "context" ? fmtNum(v.value) : (v.value ? "yes" : "no");
    return `<tr><td>${label}</td><td><strong>${shown}</strong></td><td><code>${escapeHtml(v.source || "")}</code></td>
      <td>${v.stale ? '<span class="status-chip avail-unpriced">stale</span>' : ""}</td></tr>`;
  };
  const stateChip = MI_STATE_CHIP[r.price_state] || ["avail-not_deployable", r.price_state];
  const per = (r.per_source || []).map((s) => `
    <li class="mi-src">
      <span class="${s.found ? "cap-yes" : "muted"}">${s.found ? "●" : "○"}</span>
      <strong>${escapeHtml(s.name)}</strong>
      <span class="muted small">${s.found ? "has this model" : "no entry"}${s.stale ? " · stale" : ""}</span>
    </li>`).join("");
  out.innerHTML = `
    <div class="explain-result">
      <div class="explain-head ok">
        <span class="status-chip ${stateChip[0]}">${escapeHtml(stateChip[1])}</span>
        <code>${escapeHtml(r.model)}</code>
      </div>
      <table class="mi-lookup-table">
        <thead><tr><th scope="col">Field</th><th scope="col">Value</th><th scope="col">Source</th><th scope="col">State</th></tr></thead>
        <tbody>
          ${field("Input", "input_per_million")}
          ${field("Output", "output_per_million")}
          ${field("Cache read", "cache_read_per_million")}
          ${field("Cache write", "cache_write_per_million")}
          ${field("Context", "context")}
          ${field("Tools", "tools")}
          ${field("Vision", "vision")}
          ${field("JSON mode", "json_mode")}
          ${field("JSON schema", "json_schema")}
        </tbody>
      </table>
      <p class="card-sub muted">Your configured price always wins. Catalog values are estimates, never invoices.</p>
      <ul class="mi-sources">${per}</ul>
    </div>`;
}

/** Searchable model picker for the lookup box.

    The lookup endpoint takes an exact id, which is unusable if you do not
    already know one. This filters the catalogue as you type; the free-text
    submit still works for ids that are not in the catalogue.
 */
function hideMiSuggest() {
  const list = $("#mi-lookup-suggest");
  const input = $("#mi-lookup-id");
  if (list) list.hidden = true;
  if (input) input.setAttribute("aria-expanded", "false");
}

function bindMiSuggest() {
  const input = $("#mi-lookup-id");
  const list = $("#mi-lookup-suggest");
  if (!input || !list) return;
  let active = -1;

  const render = async () => {
    const q = input.value.trim().toLowerCase();
    if (q.length < 2) { hideMiSuggest(); return; }
    if (!state.models || !state.models.length) await loadModels();
    const hits = (state.models || [])
      .filter((m) => {
        const id = (m.id || "").toLowerCase();
        return id.includes(q) || (m.provider || "").toLowerCase().includes(q);
      })
      .slice(0, 12);
    if (!hits.length) { hideMiSuggest(); return; }
    active = -1;
    list.innerHTML = hits.map((m) => `
      <li role="option" id="mi-opt-${escapeHtml(m.id)}" class="mi-suggest-item" data-mi-pick="${escapeHtml(m.id)}">
        <code>${escapeHtml(m.id)}</code>
        <span class="muted small">${escapeHtml(m.provider || "")}</span>
      </li>`).join("");
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
  };

  let timer = null;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(render, 120);
  });
  input.addEventListener("keydown", (e) => {
    if (list.hidden) return;
    const items = $$(".mi-suggest-item", list);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      active = e.key === "ArrowDown"
        ? Math.min(active + 1, items.length - 1)
        : Math.max(active - 1, 0);
      items.forEach((el, i) => el.classList.toggle("is-active", i === active));
      input.setAttribute("aria-activedescendant", items[active]?.id || "");
    } else if (e.key === "Escape") {
      hideMiSuggest();
    }
  });
  list.addEventListener("click", (e) => {
    const li = e.target.closest("[data-mi-pick]");
    if (!li) return;
    input.value = li.dataset.miPick;
    hideMiSuggest();
    $("#mi-lookup-form").requestSubmit();
  });
  document.addEventListener("click", (e) => {
    if (!list.hidden && !list.contains(e.target) && e.target !== input) hideMiSuggest();
  });
}

function bindIntelligence() {
  if (!$("#panel-intelligence")) return;
  $("#mi-add-btn").addEventListener("click", () => {
    $("#mi-form").hidden = false;
    $("#mi-name").focus();
  });
  $("#mi-cancel").addEventListener("click", () => { $("#mi-form").hidden = true; });
  $("#mi-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = $("#mi-error");
    err.hidden = true;
    try {
      await api("/v1/model-intelligence/sources", {
        method: "POST",
        body: JSON.stringify({ name: $("#mi-name").value.trim(), url: $("#mi-url").value.trim() }),
      });
      $("#mi-form").hidden = true;
      $("#mi-name").value = "";
      $("#mi-url").value = "";
      toast(t("toast.source_added"), "ok");
      await loadIntelligence();
      renderIntelligence();
    } catch (ex) {
      err.textContent = ex.message;
      err.hidden = false;
    }
  });
  $("#mi-list").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-mi-test],[data-mi-refresh],[data-mi-toggle],[data-mi-delete]");
    if (!b) return;
    const id = b.dataset.miTest || b.dataset.miRefresh || b.dataset.miToggle || b.dataset.miDelete;
    try {
      if (b.dataset.miTest) {
        b.disabled = true;
        const r = await api(`/v1/model-intelligence/sources/${id}/test`, { method: "POST", body: "{}" });
        b.disabled = false;
        toast(r.ok ? `Reachable — ${fmtNum(r.models)} models` : `Failed: ${r.error}`, r.ok ? "ok" : "err");
      } else if (b.dataset.miRefresh) {
        b.disabled = true;
        const r = await api(`/v1/model-intelligence/sources/${id}/refresh`, { method: "POST", body: "{}" });
        b.disabled = false;
        toast(r.last_error ? `Refresh failed: ${r.last_error}` : `Refreshed — ${fmtNum(r.entry_count)} models`,
          r.last_error ? "err" : "ok");
      } else if (b.dataset.miToggle) {
        await api(`/v1/model-intelligence/sources/${id}`, {
          method: "PUT", body: JSON.stringify({ is_enabled: b.dataset.on !== "true" }),
        });
      } else if (b.dataset.miDelete) {
        if (!confirm(t("confirm.delete_source"))) return;
        await api(`/v1/model-intelligence/sources/${id}`, { method: "DELETE" });
      }
      await loadIntelligence();
      renderIntelligence();
    } catch (ex) { toast(ex.message, "err"); }
  });
  bindMiSuggest();
  $("#mi-lookup-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const model = $("#mi-lookup-id").value.trim();
    if (!model) return;
    hideMiSuggest();
    try {
      const r = await api(`/v1/model-intelligence/lookup?model=${encodeURIComponent(model)}`);
      state.miLookup = r;
      renderMiLookup(r);
    } catch (ex) {
      $("#mi-lookup-result").innerHTML = `<div class="explain-result"><p>${escapeHtml(ex.message)}</p></div>`;
    }
  });
}

/* ─── routing analytics: profiles, fallback health, errors, baseline ─── */
function renderRoutingAnalyticsExtra(d) {
  _raBars("#ra-requested", (d.by_requested || []).slice(0, 8), "requested",
    (v) => (v === "auto" ? "tier-adaptive" : "tier-balanced"));

  const fb = d.fallback_stats || {};
  const el = $("#ra-fallback");
  if (el) {
    if (!fb.requests_with_attempts) {
      el.innerHTML = '<p class="muted small">No multi-attempt requests in this window.</p>';
    } else {
      const pct = fb.success_rate == null ? "—" : `${Math.round(fb.success_rate * 100)}%`;
      el.innerHTML = `
        <div class="ra-fallback-stats">
          <div><strong>${pct}</strong><span class="muted small">still succeeded</span></div>
          <div><strong>${fmtNum(fb.succeeded)} / ${fmtNum(fb.requests_with_attempts)}</strong><span class="muted small">requests</span></div>
          <div><strong>${fmtNum(fb.total_attempts)}</strong><span class="muted small">upstream attempts</span></div>
          <div><strong>${fb.avg_attempts ?? "—"}</strong><span class="muted small">avg per request</span></div>
        </div>`;
    }
  }
  _raBars("#ra-errors", (d.by_error || []).slice(0, 8), "error_type", () => "tier-error");
}

async function loadBaselineOptions() {
  try {
    const data = await api("/api/routing/models?scope=routable&limit=200&offset=0");
    const sel = $("#ra-baseline");
    sel.innerHTML = '<option value="">None</option>' + (data.models || [])
      .filter((m) => m.input_per_million != null || m.output_per_million != null)
      .map((m) => `<option value="${escapeHtml(m.id)}">${escapeHtml(m.id)}</option>`).join("");
  } catch { /* optional */ }
}

function bindBaseline() {
  const btn = $("#ra-baseline-go");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    const baseline = $("#ra-baseline").value;
    const out = $("#ra-baseline-result");
    if (!baseline) {     out.innerHTML = '<span class="muted small">Pick a model to compare against.</span>'; return; }
    out.innerHTML = '<span class="muted small">Comparing…</span>';
    try {
      const r = await api(`/v1/analytics/baseline-comparison?baseline=${encodeURIComponent(baseline)}&days=${state.windowDays}`);
      const diff = r.difference_microcents;
      const verb = diff >= 0 ? "less than" : "more than";
      out.innerHTML = `
        <p><strong>${fmtUsd(Math.abs(diff))}</strong> ${verb} paying <code>${escapeHtml(r.baseline_model)}</code>
        rates for the same tokens over ${r.days} days.</p>
        <p class="muted small">Actual ${fmtUsd(r.actual_microcents)} · at baseline ${fmtUsd(r.baseline_estimated_microcents)}
        · ${fmtNum(r.requests)} requests · <strong>estimate, not an invoice</strong></p>`;
    } catch (e) {
      out.innerHTML = `<span class="muted small">${escapeHtml(e.message)}</span>`;
    }
  });
}

/* ─────────────── Chat ─────────────── */
// The native chat tab. Everything here talks to /api/chat/* on the admin
// session; the server calls the SAME execute_chat engine SDK traffic uses,
// so routing, prompt cache and cost tracking are shared, never duplicated.
//
// Streaming: the browser reads OpenAI SSE frames straight from the engine's
// relay. The server persists the assistant row after [DONE] (or abort), so
// after the stream ends we re-fetch the conversation to reconcile ids,
// usage and cost provenance.

const CH_STREAM_API = "/api/chat";
const CH_COPY_ICON = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`;

const chState = {
  bound: false,
  conversations: [],
  convo: null,          // currently open conversation id
  messages: [],
  streaming: null,      // AbortController while a reply is in flight
  streamingText: "",
  searchSettings: null, // Settings → Chat → Web Search (admin config)
  searchOn: false,      // Per-message toggle in the composer
  attachments: [],      // Uploaded-but-unsent attachment payloads
  uploading: 0,         // Files still in flight; Send waits for 0
  attachmentLimits: null,
  dragDepth: 0,
};

const CH_ATTACHMENT_KIND_BADGE = {
  image: "IMG", document: "DOC", spreadsheet: "XLS", text: "TXT",
  code: "CODE", archive: "ZIP", video: "VID", audio: "AUD",
};

async function initChatTab() {
  if (!chState.bound) { bindChatEvents(); bindAttachmentEvents(); chState.bound = true; }
  if (!chState.settings) {
    try { chState.settings = await api(`${CH_STREAM_API}/settings`); }
    catch { chState.settings = null; }
  }
  chApplySettings();
  chLoadModels();
  chLoadSearchSettings();
  chLoadAttachmentLimits();
  chLoadConversations();
  // Keep (or re-open) the conversation the operator was reading.
  if (chState.convo) {
    try { await chRefreshConversation(); } catch { chState.convo = null; chRenderThread(); }
  }
}

function chApplySettings() {
  const s = chState.settings;
  if (!s) return;
  const thread = $("#ch-thread");
  if (thread) {
    thread.classList.remove("ch-fs-small", "ch-fs-medium", "ch-fs-large");
    thread.classList.add(`ch-fs-${s.font_size || "medium"}`);
  }
  const hint = $("#ch-kbd-hint");
  if (hint) {
    hint.textContent = s.enter_to_send
      ? t("chat.kbd_enter_send")
      : t("chat.kbd_ctrl_enter_send");
  }
  // The conversation picker falls back to the saved default.
  const sel = chModelSelect();
  if (sel && !chState.convo && s.default_model) sel.value = s.default_model;
}

function chModelSelect() {
  const host = $("#ch-model");
  if (!host) return null;
  chModelPicker();
  return host;
}

function chModelPicker() {
  const host = $("#ch-model");
  if (!host) return null;
  if (!host.gcSelect) {
    new GcSelect(host, {
      placeholderKey: "select.search_ph",
      labelFor: (v) => (v === "auto" ? t("chat.model_auto") : v),
    });
  }
  return host.gcSelect;
}

function chDefaultModelPicker() {
  const host = $("#chs-model");
  if (!host) return null;
  if (!host.gcSelect) {
    new GcSelect(host, {
      placeholderKey: "select.search_ph",
      labelFor: (v) => (v === "auto" ? t("chat.model_auto") : v),
    });
  }
  return host.gcSelect;
}

// The composer toggle only appears when an administrator configured search in
// manual mode. "auto" exists in the schema but has no server-side decision
// path yet, so it is never offered as an active choice here.
function chApplySearchSettings() {
  const s = chState.searchSettings;
  const btn = $("#ch-search-toggle");
  if (!btn) return;
  const available = !!s && s.mode === "manual" && !!s.backend;
  if (!available) {
    chState.searchOn = false;
    btn.hidden = true;
    btn.setAttribute("aria-pressed", "false");
    btn.classList.remove("is-on");
    return;
  }
  btn.hidden = false;
  btn.setAttribute("aria-pressed", chState.searchOn ? "true" : "false");
  btn.classList.toggle("is-on", chState.searchOn);
}

async function chLoadSearchSettings() {
  try { chState.searchSettings = await api("/api/chat/search-settings"); }
  catch { chState.searchSettings = null; }
  chApplySearchSettings();
}

function chFillSearchForm() {
  const s = chState.searchSettings || {};
  $("#chs-search-mode").value = s.mode || "off";
  $("#chs-search-backend").value = s.backend || "";
  $("#chs-search-url").value = s.service_url || "";
  $("#chs-search-key").value = "";
  $("#chs-search-max-searches").value = s.max_searches_per_conversation ?? 5;
  $("#chs-search-max-results").value = s.max_results ?? 5;
  $("#chs-search-max-fetches").value = s.max_page_fetches ?? 2;
  $("#chs-search-timeout").value = s.timeout_s ?? 15;
  chUpdateSearchKeyState(s.api_key_state || "unset");
  chUpdateSearchBackendRows();
}

function chUpdateSearchKeyState(keyState) {
  const el = $("#chs-search-key-state");
  if (!el) return;
  el.textContent = t(`chat.search_key_state_${keyState}`);
  el.dataset.state = keyState;
}

function chUpdateSearchBackendRows() {
  const backend = $("#chs-search-backend")?.value || "";
  const urlRow = $("#chs-search-url-row");
  const keyRow = $("#chs-search-key-row");
  if (urlRow) urlRow.hidden = backend !== "searxng";
  if (keyRow) keyRow.hidden = backend === "searxng" || backend === "";
}

function chReadSearchForm() {
  const num = (sel, fallback) => {
    const raw = $(sel)?.value ?? "";
    return raw === "" ? fallback : Number(raw);
  };
  const payload = {
    mode: $("#chs-search-mode").value,
    backend: $("#chs-search-backend").value || null,
    service_url: $("#chs-search-url").value.trim() || null,
    max_searches_per_conversation: num("#chs-search-max-searches", 5),
    max_results: num("#chs-search-max-results", 5),
    max_page_fetches: num("#chs-search-max-fetches", 2),
    timeout_s: num("#chs-search-timeout", 15),
  };
  const key = $("#chs-search-key").value.trim();
  if (key) payload.api_key = key;
  if ($("#chs-search-clear")?.dataset.clear === "1") payload.clear_api_key = true;
  return payload;
}

async function chSaveSearchSettings() {
  const payload = chReadSearchForm();
  chState.searchSettings = await api("/api/chat/search-settings", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  chApplySearchSettings();
  chFillSearchForm();
  return chState.searchSettings;
}

async function chTestSearch() {
  const btn = $("#chs-search-test");
  const status = $("#chs-search-test-status");
  if (!btn || !status) return;
  btn.disabled = true;
  status.textContent = t("chat.search_testing");
  status.dataset.state = "testing";
  try {
    await chSaveSearchSettings();
    const r = await api("/api/chat/search-settings/test", { method: "POST" });
    status.textContent = r.ok
      ? tf("chat.search_test_ok", { count: r.results ?? 0, ms: r.took_ms ?? 0 })
      : tf("chat.search_test_failed", { msg: r.error || r.code || "error" });
    status.dataset.state = r.ok ? "ok" : "err";
    toast(r.ok ? t("toast.search_saved") : t("toast.search_test_failed"), r.ok ? "ok" : "err");
  } catch (e) {
    status.textContent = tf("chat.search_test_failed", { msg: e.message });
    status.dataset.state = "err";
    toast(tf("toast.search_test_failed", { msg: e.message }), "err");
  } finally {
    btn.disabled = false;
  }
}

async function chLoadModels() {
  try {
    const data = await api("/api/routing/models?scope=routable&limit=200&offset=0");
    chState.models = data.models || [];
  } catch { chState.models = []; }
  const items = [
    { value: "auto", label: t("chat.model_auto") },
    ...chState.models.map((m) => ({ value: m.id, label: m.id })),
  ];
  for (const picker of [chModelPicker(), chDefaultModelPicker()]) {
    if (!picker) continue;
    const keep = picker.getValue();
    picker.setItems(items);
    picker.setValue(keep || "auto");
  }
}

async function chLoadConversations() {
  let data = { conversations: [] };
  try { data = await api(`${CH_STREAM_API}/conversations?limit=100`); }
  catch (e) { toast(tf("toast.chat_load_failed", { msg: e.message }), "err"); }
  chState.conversations = data.conversations || [];
  chRenderConversations();
}

function chRenderConversations() {
  const wrap = $("#ch-conversations");
  if (!wrap) return;
  if (!chState.conversations.length) {
    wrap.innerHTML = `<p class="chat-noconvos muted small">${escapeHtml(t("chat.no_conversations"))}</p>`;
    return;
  }
  wrap.innerHTML = chState.conversations.map((c) => `
    <button class="chat-convo${c.id === chState.convo ? " active" : ""}" data-convo="${escapeHtml(c.id)}" title="${escapeHtml(c.title || t("chat.default_title"))}">
      <span class="chat-convo-title">${escapeHtml(c.title || t("chat.default_title"))}</span>
      <span class="chat-convo-del icon-btn" data-convo-del="${escapeHtml(c.id)}" role="button" title="${escapeHtml(t("chat.delete_convo_title"))}" aria-label="${escapeHtml(t("chat.delete_convo_title"))}">×</span>
    </button>`).join("");
}

async function chOpen(id) {
  chState.convo = id;
  chRenderConversations();
  await chRefreshConversation();
  // Show the conversation's own model, falling back to the default.
  const c = chState.conversations.find((x) => x.id === id);
  const sel = chModelSelect();
  if (c?.model && sel) sel.value = c.model;
  $("#ch-input").focus();
}

async function chRefreshConversation() {
  if (!chState.convo) return;
  const data = await api(`${CH_STREAM_API}/conversations/${encodeURIComponent(chState.convo)}`);
  chState.messages = data.messages || [];
  chSetHeader(data.conversation);
  $("#ch-regen").disabled = !chState.messages.some((m) => m.role === "assistant");
  chRenderThread({ restoreScroll: true });
}

function chSetHeader(convo) {
  $("#ch-title").textContent = convo.title || t("chat.default_title");
  const sys = convo.system_prompt;
  $("#ch-sysprompt").textContent = sys ? t("chat.system_prompt_set") : t("chat.system_prompt");
}

function chRenderThread({ restoreScroll = false } = {}) {
  const thread = $("#ch-thread");
  if (!thread) return;
  const prevBottom = restoreScroll ? thread.scrollHeight - thread.scrollTop : 0;
  if (!chState.messages.length) {
    thread.innerHTML = `<div class="chat-empty" id="ch-empty">
      <p class="chat-empty-title">${escapeHtml(t("chat.empty_title"))}</p>
      <p class="muted">${escapeHtml(t("chat.empty_sub"))}</p>
    </div>`;
    $("#ch-empty").scrollIntoView();
    return;
  }
  thread.innerHTML = chState.messages.map((m, i) => chRenderMessage(m, i)).join("");
  thread.scrollTop = restoreScroll ? Math.max(0, thread.scrollHeight - prevBottom) : thread.scrollHeight;
}

function chRenderMessage(m, index) {
  if (m.role === "user") {
    return `<div class="chat-msg chat-msg-user">${chAttachmentChips(m.attachments, { readonly: true })}<div class="chat-bubble">${chMarkdown(m.content || "")}</div></div>`;
  }
  const meta = [];
  if (m.model_resolved) meta.push(`<code>${escapeHtml(m.model_resolved)}</code>`);
  if (m.provider) meta.push(escapeHtml(m.provider));
  if (m.input_tokens != null || m.output_tokens != null) {
    meta.push(tf("chat.tokens_meta", { in: m.input_tokens ?? "—", out: m.output_tokens ?? "—" }));
  }
  if (m.cost_microcents != null) meta.push(fmtUsd(m.cost_microcents));
  if (m.error_type) meta.push(escapeHtml(m.error_type));
  if (m.search_backend) meta.push(tf("chat.search_used", { backend: escapeHtml(m.search_backend) }));
  const last = index === chState.messages.length - 1;
  return `<div class="chat-msg chat-msg-assistant">
    <div class="chat-bubble">${chMarkdown(m.content || "")}${m.error_type ? `<p class="chat-error-note">${escapeHtml(t("chat.error_note"))}</p>` : ""}${chCitations(m.citations)}</div>
    <div class="chat-meta">${meta.length ? meta.join(" · ") : ""}${last ? `<button class="chat-copy icon-btn" title="${escapeHtml(t("ui.copy"))}" aria-label="${escapeHtml(t("ui.copy"))}">${CH_COPY_ICON}</button>` : ""}</div>
  </div>`;
}

// Sources are server-fetched, but the title/URL still came from the open web:
// only http(s) links are emitted and everything is escaped.
function chCitations(citations) {
  if (!Array.isArray(citations) || !citations.length) return "";
  const items = citations.map((c) => {
    const url = typeof c.url === "string" ? c.url : "";
    if (!/^https?:\/\//i.test(url)) return "";
    const title = escapeHtml(c.title || url);
    return `<li><a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${title}</a></li>`;
  }).filter(Boolean);
  if (!items.length) return "";
  return `<div class="chat-citations"><span class="chat-citations-title">${escapeHtml(t("chat.sources"))}</span><ol>${items.join("")}</ol></div>`;
}

// Deliberately tiny markdown: fenced code, inline code, bold/italic, links.
// Anything else renders as plain text — a chat pane is not a web page.
function chMarkdown(text) {
  let out = "";
  const parts = String(text).split(/```/);
  for (let i = 0; i < parts.length; i++) {
    if (i % 2 === 1) {
      const nl = parts[i].indexOf("\n");
      const lang = nl > -1 && nl <= 12 ? parts[i].slice(0, nl).trim() : "";
      const code = nl > -1 && lang ? parts[i].slice(nl + 1) : parts[i];
      out += `<pre class="chat-code"><code>${escapeHtml(code.replace(/\n$/, ""))}</code>` +
        `<button class="chat-code-copy icon-btn" title="${escapeHtml(t("ui.copy"))}" aria-label="${escapeHtml(t("ui.copy"))}">${CH_COPY_ICON}</button></pre>`;
      continue;
    }
    out += escapeHtml(parts[i])
      .replace(/`([^`\n]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
      .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>')
      .replace(/\n/g, "<br>");
  }
  return out;
}

function chAttachmentChipList(refs, { readonly = false } = {}) {
  return (refs || []).map((ref) => {
    const kind = escapeHtml(ref.kind || "text");
    const badge = CH_ATTACHMENT_KIND_BADGE[ref.kind] || "FILE";
    // Thumbnails are server-rendered data URLs; anything else is skipped
    // rather than injected into an <img src>.
    const thumb = typeof ref.thumbnail === "string" && /^data:image\//i.test(ref.thumbnail)
      ? `<img class="chat-attachment-thumb" src="${escapeHtml(ref.thumbnail)}" alt="">`
      : `<span class="chat-attachment-badge" aria-hidden="true">${escapeHtml(badge)}</span>`;
    const size = chFormatBytes(ref.size);
    const name = escapeHtml(ref.name || "file");
    // An upload the server stored but could not read stays attachable (the
    // model is told it could not be read), so it is marked on the chip
    // itself rather than only in a toast that disappears.
    const state = ref.extraction || ref.extraction_state;
    const failed = state === "failed" || state === "unsupported";
    const problem = failed ? escapeHtml(ref.error || t("chat.attach_unreadable")) : "";
    const warn = failed
      ? `<span class="chat-attachment-warn" role="img" aria-label="${problem}" title="${problem}">!</span>`
      : "";
    const del = readonly
      ? ""
      : `<button type="button" class="chat-attachment-del icon-btn" data-attachment-remove="${escapeHtml(ref.id)}" title="${escapeHtml(t("chat.attach_remove"))}" aria-label="${escapeHtml(t("chat.attach_remove"))}">×</button>`;
    return `<span class="chat-attachment-chip${failed ? " is-failed" : ""}" data-kind="${kind}" title="${name} · ${size}${failed ? ` · ${problem}` : ""}">
      ${thumb}
      <span class="chat-attachment-name">${name}</span>
      <span class="chat-attachment-size">${escapeHtml(size)}</span>${warn}${del}
    </span>`;
  }).join("");
}

function chAttachmentChips(refs, opts = {}) {
  if (!Array.isArray(refs) || !refs.length) return "";
  return `<div class="chat-attachment-chips">${chAttachmentChipList(refs, opts)}</div>`;
}

function chFormatBytes(n) {
  if (n == null || Number.isNaN(Number(n))) return "";
  const bytes = Number(n);
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function chLoadAttachmentLimits() {
  if (!chState.attachmentLimits) {
    try {
      chState.attachmentLimits = await api(`${CH_STREAM_API}/attachments/limits`);
    } catch {
      // A failed request (session not ready yet, network blip) is NOT the
      // server saying "disabled". Caching it as disabled hid the paperclip
      // for the rest of the page's life; leave it unknown so the next visit
      // or the next upload attempt asks again.
      chState.attachmentLimits = null;
    }
  }
  const btn = $("#ch-attach");
  // Only an explicit `enabled: false` from the server hides the control.
  if (btn) btn.hidden = chState.attachmentLimits?.enabled === false;
  chRenderAttachments();
  return chState.attachmentLimits;
}

function chRenderAttachments() {
  const host = $("#ch-attachments");
  if (!host) return;
  const busy = chState.uploading > 0;
  const hasItems = chState.attachments.length > 0 || busy;
  host.hidden = !hasItems;
  const pending = busy
    ? `<span class="chat-attachment-chip is-uploading"><span class="chat-attachment-badge" aria-hidden="true">···</span><span class="chat-attachment-name">${escapeHtml(t("chat.attach_uploading"))}</span></span>`
    : "";
  host.innerHTML = pending + chAttachmentChipList(chState.attachments);
  // Send cannot go out while files are still uploading (chSend would only
  // toast "wait"); show that state on the button itself. While a reply is
  // streaming the same button is Stop and must stay clickable.
  const send = $("#ch-send");
  if (send && !chState.streaming) {
    send.disabled = busy;
    send.setAttribute("aria-busy", busy ? "true" : "false");
  }
}

function chAttachmentError(files, message) {
  toast(tf("toast.chat_attach_failed", {
    name: files.length === 1 ? files[0].name : `${files.length} files`,
    msg: message,
  }), "err", 4200);
}

async function chUploadFiles(files) {
  const list = Array.from(files || []);
  if (!list.length) return;
  const limits = chState.attachmentLimits || await chLoadAttachmentLimits();
  if (limits && limits.enabled === false) {
    toast(t("toast.chat_attach_disabled"), "err");
    return;
  }
  const maxPer = limits?.max_per_message ?? 8;
  const room = Math.max(0, maxPer - chState.attachments.length - chState.uploading);
  if (list.length > room) {
    toast(tf("toast.chat_attach_too_many", { max: maxPer }), "err");
  }
  const maxMb = limits?.max_mb;
  for (const file of list.slice(0, room)) {
    if (maxMb && file.size > maxMb * 1024 * 1024) {
      chAttachmentError([file], tf("chat.attach_too_large", { max: maxMb }));
      continue;
    }
    chState.uploading += 1;
    chRenderAttachments();
    try {
      const form = new FormData();
      form.append("file", file, file.name);
      const res = await fetch(`${CH_STREAM_API}/attachments`, {
        method: "POST",
        headers: state.csrfToken ? { "X-CSRF-Token": state.csrfToken } : {},
        credentials: "same-origin",
        body: form,
      });
      let payload = null;
      try { payload = await res.json(); } catch { /* keep */ }
      if (!res.ok) {
        const msg = payload?.error?.message || payload?.detail || res.statusText;
        chAttachmentError([file], msg);
        continue;
      }
      const att = payload.attachment;
      chState.attachments.push(att);
      if ((att?.extraction === "failed" || att?.extraction === "unsupported") && att.error) {
        toast(tf("toast.chat_attach_extract_failed", { name: att.name, msg: att.error }), "info", 5200);
      }
    } catch (e) {
      chAttachmentError([file], e.message);
    } finally {
      chState.uploading -= 1;
      chRenderAttachments();
    }
  }
}

async function chRemoveAttachment(id) {
  const idx = chState.attachments.findIndex((a) => a.id === id);
  if (idx < 0) return;
  chState.attachments.splice(idx, 1);
  chRenderAttachments();
  try {
    await api(`${CH_STREAM_API}/attachments/${encodeURIComponent(id)}`, { method: "DELETE" });
  } catch { /* orphan sweeper cleans it up; keep the UI consistent */ }
}

function chClearAttachments() {
  chState.attachments = [];
  chState.uploading = 0;
  chRenderAttachments();
}

const CH_IMAGE_EXT = {
  "image/png": "png", "image/jpeg": "jpg", "image/gif": "gif",
  "image/webp": "webp", "image/bmp": "bmp", "image/tiff": "tiff",
};

/** Files on a paste event, each with a name the server can classify.
 *
 *  The server decides the type from the extension and then checks the magic
 *  bytes. A screenshot on the clipboard often arrives without a usable name
 *  ("" or "blob", depending on browser and screenshot tool), which the server
 *  rightly rejects as an unknown type. Name such images from their MIME type;
 *  the bytes are still verified server-side. `clipboardData.files` is read
 *  first because some browsers expose a pasted image there but not as an
 *  item; items are the fallback. */
function chClipboardFiles(data) {
  if (!data) return [];
  let files = Array.from(data.files || []);
  if (!files.length) {
    files = Array.from(data.items || [])
      .filter((it) => it.kind === "file")
      .map((it) => it.getAsFile())
      .filter(Boolean);
  }
  const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\..*$/, "").replace("T", "-");
  return files.map((file, i) => {
    const ext = CH_IMAGE_EXT[(file.type || "").toLowerCase()];
    const named = /\.[a-z0-9]{1,8}$/i.test(file.name || "");
    if (!ext || named) return file;
    const suffix = files.length > 1 ? `-${i + 1}` : "";
    return new File([file], `pasted-image-${stamp}${suffix}.${ext}`, { type: file.type });
  });
}

function chDragHasFiles(e) {
  const types = e.dataTransfer?.types;
  return !!types && Array.from(types).includes("Files");
}

function chSetDropOverlay(on) {
  const el = $("#ch-drop-overlay");
  if (el) el.hidden = !on;
}

function bindAttachmentEvents() {
  const pickBtn = $("#ch-attach");
  const fileInput = $("#ch-file-input");
  if (pickBtn && fileInput) {
    pickBtn.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", async () => {
      const files = Array.from(fileInput.files || []);
      fileInput.value = "";
      await chUploadFiles(files);
    });
  }
  const wrap = $(".chat-wrap");
  if (wrap) {
    wrap.addEventListener("dragenter", (e) => {
      if (!chDragHasFiles(e)) return;
      e.preventDefault();
      chState.dragDepth += 1;
      chSetDropOverlay(true);
    });
    wrap.addEventListener("dragover", (e) => {
      if (!chDragHasFiles(e)) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
    });
    wrap.addEventListener("dragleave", (e) => {
      if (!chDragHasFiles(e)) return;
      chState.dragDepth = Math.max(0, chState.dragDepth - 1);
      if (chState.dragDepth === 0) chSetDropOverlay(false);
    });
    wrap.addEventListener("drop", async (e) => {
      if (!chDragHasFiles(e)) return;
      e.preventDefault();
      chState.dragDepth = 0;
      chSetDropOverlay(false);
      await chUploadFiles(e.dataTransfer.files);
    });
  }
  const input = $("#ch-input");
  if (input) {
    input.addEventListener("paste", async (e) => {
      const files = chClipboardFiles(e.clipboardData);
      if (!files.length) return; // plain text paste stays native
      e.preventDefault();
      await chUploadFiles(files);
    });
  }
  const host = $("#ch-attachments");
  if (host) {
    host.addEventListener("click", (e) => {
      const del = e.target.closest("[data-attachment-remove]");
      if (del) chRemoveAttachment(del.dataset.attachmentRemove);
    });
  }
}

function chShowAttachmentNotice(res) {
  const notes = res?.headers?.get("x-geek-attachment-notes");
  if (!notes) return;
  toast(notes, "info", 5200);
}

async function chNewChat() {
  try {
    const convo = await api(`${CH_STREAM_API}/conversations`, {
      method: "POST",
      body: JSON.stringify({ model: chModelSelect()?.value || "auto" }),
    });
    chState.conversations.unshift(convo);
    chState.messages = [];
    chState.convo = convo.id;
    chClearAttachments();
    chRenderConversations();
    chSetHeader(convo);
    chRenderThread();
    $("#ch-input").focus();
  } catch (e) { toast(tf("toast.chat_failed", { msg: e.message }), "err"); }
}

function chSetStreaming(on) {
  const btn = $("#ch-send");
  const input = $("#ch-input");
  $("#ch-regen").disabled = on || !chState.messages.some((m) => m.role === "assistant");
  if (on) {
    btn.textContent = t("chat.stop");
    btn.classList.add("btn-danger");
    input.disabled = true;
  } else {
    btn.textContent = t("chat.send");
    btn.classList.remove("btn-danger");
    input.disabled = false;
    input.focus();
  }
}

function chShowContextWindow(res) {
  const el = $("#ch-materialized");
  if (!el) return;
  const budget = res?.headers?.get("x-geek-context-budget");
  const omitted = res?.headers?.get("x-geek-context-omitted");
  const tokens = res?.headers?.get("x-geek-context-tokens");
  const parts = [];
  if (budget != null && tokens != null) {
    parts.push(tf("chat.context_budget", { tokens, budget }));
  }
  if (omitted != null && Number(omitted) > 0) {
    parts.push(tf("chat.context_omitted", { count: omitted }));
  }
  if (!parts.length) { el.hidden = true; el.textContent = ""; return; }
  el.hidden = false;
  el.textContent = parts.join(" · ");
  el.title = parts.join("\n");
}

function chAppendUserBubble(content, attachments = []) {
  const thread = $("#ch-thread");
  thread.querySelector(".chat-empty")?.remove();
  const el = document.createElement("div");
  el.className = "chat-msg chat-msg-user";
  el.innerHTML = `${chAttachmentChips(attachments, { readonly: true })}<div class="chat-bubble">${chMarkdown(content)}</div>`;
  thread.appendChild(el);
  thread.scrollTop = thread.scrollHeight;
}

function chPendingAssistant() {
  const thread = $("#ch-thread");
  const el = document.createElement("div");
  el.className = "chat-msg chat-msg-assistant";
  el.innerHTML = `<div class="chat-bubble"><span class="chat-typing"><span></span><span></span><span></span></span></div><div class="chat-meta"></div>`;
  thread.appendChild(el);
  thread.scrollTop = thread.scrollHeight;
  return el;
}

function chRenderPartial(el) {
  const bubble = el.querySelector(".chat-bubble");
  const text = chState.streamingText;
  bubble.innerHTML = text ? chMarkdown(text) :
    `<span class="chat-typing"><span></span><span></span><span></span></span>`;
  const thread = $("#ch-thread");
  thread.scrollTop = thread.scrollHeight;
}

// Shared SSE reader: walks data: frames, appends delta content, resolves the
// engine's model when the first chunk names one. Returns the error message
// from any `data: {"error": ...}` frame the backend forwarded upstream.
async function chReadStream(res, onText) {
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let errMsg = null;
  for (;;) {
    const { done: eof, value } = await reader.read();
    if (eof) break;
    buf += decoder.decode(value, { stream: true });
    let sep;
    while ((sep = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      for (const line of frame.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        const payload = line.slice(6);
        if (payload === "[DONE]") continue;
        try {
          const obj = JSON.parse(payload);
          if (obj.error) { errMsg = obj.error.message || t("chat.upstream_error"); continue; }
          const piece = obj.choices?.[0]?.delta?.content;
          if (typeof piece === "string" && piece) onText(piece, obj);
        } catch { /* lines are complete frames; only a dropped byte could land here */ }
      }
    }
  }
  return errMsg;
}

function chStreamHeaders() {
  return {
    "Content-Type": "application/json",
    ...(state.csrfToken ? { "X-CSRF-Token": state.csrfToken } : {}),
  };
}

async function chSend() {
  const input = $("#ch-input");
  if (chState.streaming) { chStop(); return; }
  const content = input.value.trim();
  if (chState.uploading > 0) { toast(t("toast.chat_attach_wait"), "info"); return; }
  if (!content && !chState.attachments.length) return;
  const sentAttachments = chState.attachments.slice();
  const attachmentIds = sentAttachments.map((a) => a.id);
  let convo = chState.convo;
  if (!convo) {
    try {
      const created = await api(`${CH_STREAM_API}/conversations`, {
        method: "POST",
        body: JSON.stringify({ model: chModelSelect()?.value || "auto" }),
      });
      convo = created.id;
      chState.conversations.unshift(created);
      chState.convo = created.id;
      chSetHeader(created);
      chRenderConversations();
    } catch (e) { toast(tf("toast.chat_failed", { msg: e.message }), "err"); return; }
  }
  input.value = "";
  input.style.height = "";
  chAppendUserBubble(content, sentAttachments);
  // Optimistically clear: the send below either accepts them or restores on error.
  chClearAttachments();

  const model = chModelSelect()?.value || "auto";
  const controller = new AbortController();
  chState.streaming = controller;
  chState.streamingText = "";
  const pending = chPendingAssistant();
  chSetStreaming(true);
  let err = null;
  let accepted = false;
  const restoreAttachments = () => {
    if (!accepted && !chState.attachments.length && sentAttachments.length) {
      chState.attachments = sentAttachments;
      chRenderAttachments();
    }
  };
  try {
    const res = await fetch(`${CH_STREAM_API}/conversations/${encodeURIComponent(convo)}/messages`, {
      method: "POST",
      headers: chStreamHeaders(),
      credentials: "same-origin",
      body: JSON.stringify({
        content, model, stream: true,
        web_search: !!chState.searchOn,
        attachment_ids: attachmentIds,
      }),
      signal: controller.signal,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json())?.error?.message || detail; } catch { /* keep */ }
      throw new Error(detail);
    }
    accepted = true;
    chShowContextWindow(res);
    chShowAttachmentNotice(res);
    err = await chReadStream(res, (piece, obj) => {
      chState.streamingText += piece;
      if (obj.model) chState.lastResolved = obj.model;
      chRenderPartial(pending);
    });
  } catch (e) {
    if (e.name !== "AbortError") err = e.message;
    // AbortError: the server persisted the partial answer; sync below.
  } finally {
    chState.streaming = null;
    // Reconcile with the server's persisted rows (ids, usage, cost, partials).
    try { await chRefreshConversation(); } catch { /* tab navigated away */ }
    chSetStreaming(false);
    if (err) {
      // A pre-send rejection (no vision, missing attachment, budget) never
      // bound the files, so put them back so the operator can retry.
      if (sentAttachments.length) restoreAttachments();
      toast(tf("toast.chat_failed", { msg: err }), "err", 4200);
    }
  }
}

function chStop() {
  if (chState.streaming) chState.streaming.abort();
}

async function chRegenerate() {
  if (!chState.convo) return;
  if (chState.streaming) { chStop(); return; }
  const convo = chState.convo;
  const model = chModelSelect()?.value || "auto";
  chState.streaming = new AbortController();
  chState.streamingText = "";
  const pending = chPendingAssistant();
  chSetStreaming(true);
  let err = null;
  try {
    const res = await fetch(`${CH_STREAM_API}/conversations/${encodeURIComponent(convo)}/regenerate`, {
      method: "POST",
      headers: chStreamHeaders(),
      credentials: "same-origin",
      body: JSON.stringify({ model, stream: true }),
      signal: chState.streaming.signal,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json())?.error?.message || detail; } catch { /* keep */ }
      throw new Error(detail);
    }
    chShowContextWindow(res);
    chShowAttachmentNotice(res);
    err = await chReadStream(res, (piece, obj) => {
      chState.streamingText += piece;
      if (obj.model) chState.lastResolved = obj.model;
      chRenderPartial(pending);
    });
  } catch (e) {
    if (e.name !== "AbortError") err = e.message;
  } finally {
    chState.streaming = null;
    try { await chRefreshConversation(); } catch { /* ignore */ }
    chSetStreaming(false);
    if (err) toast(tf("toast.chat_failed", { msg: err }), "err", 4200);
  }
}

async function chDeleteConvo(id) {
  if (!confirm(tf("confirm.delete_conversation"))) return;
  try {
    await api(`${CH_STREAM_API}/conversations/${encodeURIComponent(id)}`, { method: "DELETE" });
    chState.conversations = chState.conversations.filter((c) => c.id !== id);
    if (chState.convo === id) {
      chState.convo = null;
      chState.messages = [];
      $("#ch-title").textContent = t("chat.default_title");
      chRenderThread();
    }
    chRenderConversations();
    toast(t("toast.chat_convo_deleted"));
  } catch (e) { toast(tf("toast.chat_failed", { msg: e.message }), "err"); }
}

async function chClearAll() {
  if (!confirm(t("confirm.clear_chat_history"))) return;
  try {
    const r = await api(`${CH_STREAM_API}/history/clear`, {
      method: "POST",
      body: JSON.stringify({ confirm: true }),
    });
    chState.conversations = [];
    chState.convo = null;
    chState.messages = [];
    $("#ch-title").textContent = t("chat.default_title");
    chRenderConversations();
    chRenderThread();
    toast(tf("toast.chat_cleared", { count: r.cleared }));
  } catch (e) { toast(tf("toast.chat_failed", { msg: e.message }), "err"); }
}

async function chOpenSettings() {
  const s = chState.settings || {};
  await chLoadModels();
  await chLoadSearchSettings();
  chFillSearchForm();
  chDefaultModelPicker()?.setValue(s.default_model || "auto");
  $("#chs-temperature").value = s.temperature ?? "";
  $("#chs-max-tokens").value = s.max_tokens ?? "";
  $("#chs-system").value = s.system_prompt || "";
  $("#chs-save-history").checked = !!s.save_history;
  $("#chs-retention").value = s.retention_days ?? "";
  $("#chs-font").value = s.font_size || "medium";
  $("#chs-enter-send").checked = s.enter_to_send !== false;
  $("#chs-privacy-ack").checked = !!s.privacy_notice_ack;
  $("#chat-settings-dialog").showModal();
}

async function chSaveSettings() {
  const temperature = $("#chs-temperature").value === "" ? null : Number($("#chs-temperature").value);
  const maxTokens = $("#chs-max-tokens").value === "" ? null : Number($("#chs-max-tokens").value);
  const retention = $("#chs-retention").value === "" ? null : Number($("#chs-retention").value);
  if (temperature != null && (temperature < 0 || temperature > 2)) {
    toast(t("toast.chat_temp_range"), "err"); return;
  }
  try {
    chState.settings = await api(`${CH_STREAM_API}/settings`, {
      method: "PUT",
      body: JSON.stringify({
        default_model: chDefaultModelPicker()?.getValue() || null,
        temperature,
        max_tokens: maxTokens,
        system_prompt: $("#chs-system").value.trim() || null,
        save_history: $("#chs-save-history").checked,
        retention_days: retention,
        font_size: $("#chs-font").value,
        enter_to_send: $("#chs-enter-send").checked,
        privacy_notice_ack: $("#chs-privacy-ack").checked,
      }),
    });
    chApplySettings();
    try { await chSaveSearchSettings(); }
    catch (e) { toast(tf("toast.search_save_failed", { msg: e.message }), "err"); return; }
    $("#chat-settings-dialog").close();
    toast(t("toast.chat_settings_saved"));
  } catch (e) { toast(tf("toast.chat_failed", { msg: e.message }), "err"); }
}

async function chOpenSystemPrompt() {
  if (!chState.convo) { toast(t("toast.chat_open_convo"), "err"); return; }
  try {
    const data = await api(`${CH_STREAM_API}/conversations/${encodeURIComponent(chState.convo)}`);
    $("#chd-system").value = data.conversation.system_prompt || "";
  } catch { $("#chd-system").value = ""; }
  $("#chat-system-dialog").showModal();
}

async function chSaveSystemPrompt() {
  const value = $("#chd-system").value.trim() || null;
  try {
    const convo = await api(`${CH_STREAM_API}/conversations/${encodeURIComponent(chState.convo)}`, {
      method: "PATCH", body: JSON.stringify({ system_prompt: value }),
    });
    const i = chState.conversations.findIndex((c) => c.id === convo.id);
    if (i >= 0) chState.conversations[i] = { ...chState.conversations[i], ...convo };
    chSetHeader(convo);
    $("#chat-system-dialog").close();
    toast(t("toast.chat_saved_prompt"));
  } catch (e) { toast(tf("toast.chat_failed", { msg: e.message }), "err"); }
}

function bindChatEvents() {
  $("#ch-new").addEventListener("click", chNewChat);
  $("#ch-settings").addEventListener("click", chOpenSettings);
  $("#ch-clear").addEventListener("click", chClearAll);
  $("#ch-send").addEventListener("click", chSend);
  $("#ch-regen").addEventListener("click", chRegenerate);
  $("#ch-sysprompt").addEventListener("click", chOpenSystemPrompt);
  $("#chs-save").addEventListener("click", chSaveSettings);
  $("#chs-search-backend").addEventListener("change", chUpdateSearchBackendRows);
  $("#chs-search-test").addEventListener("click", chTestSearch);
  $("#chs-search-clear").addEventListener("click", () => {
    const btn = $("#chs-search-clear");
    btn.dataset.clear = btn.dataset.clear === "1" ? "0" : "1";
    btn.classList.toggle("btn-danger", btn.dataset.clear === "1");
    chUpdateSearchKeyState(btn.dataset.clear === "1" ? "unset" : (chState.searchSettings?.api_key_state || "unset"));
  });
  $("#ch-search-toggle").addEventListener("click", () => {
    if (!chState.searchSettings || chState.searchSettings.mode !== "manual") return;
    chState.searchOn = !chState.searchOn;
    chApplySearchSettings();
  });
  $("#chd-save").addEventListener("click", chSaveSystemPrompt);
  $("#ch-model").addEventListener("change", async (e) => {
    if (!chState.convo) return;
    try {
      const convo = await api(`${CH_STREAM_API}/conversations/${encodeURIComponent(chState.convo)}`, {
        method: "PATCH", body: JSON.stringify({ model: e.target.value }),
      });
      const i = chState.conversations.findIndex((c) => c.id === convo.id);
      if (i >= 0) chState.conversations[i] = { ...chState.conversations[i], model: convo.model };
      chRenderConversations();
    } catch (err) { toast(tf("toast.chat_failed", { msg: err.message }), "err"); }
  });
  const input = $("#ch-input");
  input.addEventListener("keydown", (e) => {
    // Enter that confirms an IME composition (Chinese, Japanese, Korean
    // input) belongs to the input method, not to the composer: sending
    // here submitted a half-typed message. keyCode 229 covers browsers that
    // report the composition only that way.
    if (e.isComposing || e.keyCode === 229) return;
    const enterToSend = chState.settings ? chState.settings.enter_to_send !== false : true;
    if (e.key === "Enter" && !e.shiftKey && enterToSend) { e.preventDefault(); chSend(); }
    else if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && !enterToSend) { e.preventDefault(); chSend(); }
  });
  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 200)}px`;
  });
  $("#ch-conversations").addEventListener("click", (e) => {
    const del = e.target.closest("[data-convo-del]");
    if (del) {
      e.stopPropagation();
      e.preventDefault();
      chDeleteConvo(del.dataset.convoDel);
      return;
    }
    const btn = e.target.closest("[data-convo]");
    if (btn) chOpen(btn.dataset.convo);
  });
  $("#ch-menu-btn").addEventListener("click", () => {
    $("#chat-side").classList.toggle("open");
  });
  $("#ch-thread").addEventListener("click", (e) => {
    const btn = e.target.closest(".chat-code-copy, .chat-copy");
    if (!btn) return;
    const code = btn.closest("pre")?.querySelector("code")
      ?? btn.closest(".chat-msg-assistant")?.querySelector(".chat-bubble");
    if (!code) return;
    copyToClipboard(code.textContent, btn);
  });
  document.addEventListener("click", (e) => {
    if (!$("#chat-side")?.classList.contains("open")) return;
    if (!e.target.closest("#chat-side") && !e.target.closest("#ch-menu-btn")) {
      $("#chat-side").classList.remove("open");
    }
  });
  // Escape stops generation (mirrors terminal chat conventions).
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && chState.streaming) chStop();
  });
}


/* ==========================================================================
   LOCAL AI CONNECT
   ==========================================================================
   A machine is one outbound connector dialling this server over a WebSocket.
   Nothing here opens an inbound port: the whole feature exists so an admin can
   keep their own hardware serving models without exposing it to the internet.
   The wizard is intentionally linear and state-driven — each step is a single
   fact read from the overview payload, so a returning admin resumes where the
   actual server state says they are, not where a browser cookie says.
*/
state.local = {
  overview: null,
  enrollments: [],
  serviceFiles: null,
  serviceKind: "systemd",
  wizardStep: 0,
  wizardCode: null,
  wizardName: "",
  credentialOnly: false,
  pollTimer: null,
};

const LOCAL_WIZARD_STEPS = 8;

async function loadLocalConnect() {
  try {
    const [overview, enrollments, serviceFiles] = await Promise.all([
      api("/api/local-connect/overview"),
      api("/api/local-connect/enrollments").catch(() => ({ enrollments: [] })),
      api("/api/local-connect/service-files").catch(() => null),
    ]);
    state.local.overview = overview;
    state.local.enrollments = enrollments?.enrollments || [];
    state.local.serviceFiles = serviceFiles;
  } catch (e) {
    state.local.overview = null;
  }
}

function _localMachineStatusPill(machine) {
  if (machine.status === "revoked") return `<span class="pill err">${escapeHtml(t("local.status_revoked"))}</span>`;
  if (machine.status === "pending") return `<span class="pill warn">${escapeHtml(t("local.status_pending"))}</span>`;
  if (machine.online) return `<span class="pill ok">${escapeHtml(t("local.status_online"))}</span>`;
  return `<span class="pill muted">${escapeHtml(t("local.status_offline"))}</span>`;
}

function _localModelRow(machine, model) {
  const caps = [];
  if (model.supports_tools) caps.push("tools");
  if (model.supports_vision) caps.push("vision");
  if (model.supports_json_mode) caps.push("json");
  const price = model.context_length
    ? `${fmtNum(model.context_length)} ${t("local.ctx_suffix")}`
    : t("local.ctx_unknown");
  return `
    <tr class="row-in">
      <td>
        <div class="local-model-name">${escapeHtml(model.display_name || model.model_key)}</div>
        <code class="local-model-id">${escapeHtml(model.routing_id)}</code>
      </td>
      <td><span class="proto-badge">${escapeHtml(model.adapter)}</span></td>
      <td class="muted small">${escapeHtml(price)}</td>
      <td>${caps.length ? caps.map((c) => `<span class="chip">${escapeHtml(c)}</span>`).join(" ") : '<span class="muted small">—</span>'}</td>
      <td class="th-actions">
        <label class="checkline local-model-toggle">
          <input type="checkbox" data-local-toggle-model="${escapeHtml(model.id)}" data-machine="${escapeHtml(machine.id)}" ${model.is_enabled ? "checked" : ""}>
        </label>
      </td>
    </tr>`;
}

function _localMachineCard(machine) {
  const pending = machine.status === "pending";
  const revoked = machine.status === "revoked";
  const models = machine.models || [];
  const actions = [];
  if (pending) {
    actions.push(`<button type="button" class="btn btn-primary btn-sm" data-local-action="approve" data-id="${escapeHtml(machine.id)}">${escapeHtml(t("local.action_approve"))}</button>`);
  }
  if (!pending && !revoked) {
    actions.push(`<button type="button" class="btn btn-ghost btn-sm" data-local-action="discover" data-id="${escapeHtml(machine.id)}" ${machine.online ? "" : "disabled"}>${escapeHtml(t("local.action_discover"))}</button>`);
    actions.push(`<button type="button" class="btn btn-ghost btn-sm" data-local-action="revoke" data-id="${escapeHtml(machine.id)}">${escapeHtml(t("local.action_revoke"))}</button>`);
  }
  if (revoked) {
    actions.push(`<button type="button" class="btn btn-ghost btn-sm" data-local-action="rotate" data-id="${escapeHtml(machine.id)}">${escapeHtml(t("local.action_rotate"))}</button>`);
  }
  actions.push(`<button type="button" class="btn btn-ghost btn-sm btn-danger" data-local-action="delete" data-id="${escapeHtml(machine.id)}">${escapeHtml(t("local.action_delete"))}</button>`);

  const meta = [];
  if (machine.hostname) meta.push(`<div><dt>${escapeHtml(t("local.meta_host"))}</dt><dd><code>${escapeHtml(machine.hostname)}</code></dd></div>`);
  if (machine.platform) meta.push(`<div><dt>${escapeHtml(t("local.meta_platform"))}</dt><dd>${escapeHtml(machine.platform)}</dd></div>`);
  if (machine.agent_version) meta.push(`<div><dt>${escapeHtml(t("local.meta_agent"))}</dt><dd>${escapeHtml(machine.agent_version)}</dd></div>`);
  if (machine.adapters?.length) meta.push(`<div><dt>${escapeHtml(t("local.meta_adapters"))}</dt><dd>${machine.adapters.map((a) => `<span class="chip">${escapeHtml(a)}</span>`).join(" ")}</dd></div>`);
  meta.push(`<div><dt>${escapeHtml(t("local.meta_seen"))}</dt><dd>${machine.last_seen_at ? escapeHtml(_fmtWhen(machine.last_seen_at)) : escapeHtml(t("local.never"))}</dd></div>`);

  return `
    <div class="local-machine" data-machine-id="${escapeHtml(machine.id)}">
      <div class="local-machine-head">
        <div class="local-machine-title">
          <h3>${escapeHtml(machine.display_name || machine.hostname || machine.id)}</h3>
          ${_localMachineStatusPill(machine)}
        </div>
        <div class="local-machine-actions">${actions.join("")}</div>
      </div>
      <div class="meta-list local-machine-meta">${meta.join("")}</div>
      ${pending ? `<p class="callout callout-warn">${escapeHtml(t("local.pending_note"))}</p>` : ""}
      ${models.length ? `
        <div class="table-wrap local-model-table">
          <table>
            <thead><tr>
              <th>${escapeHtml(t("local.col_model"))}</th>
              <th>${escapeHtml(t("local.col_adapter"))}</th>
              <th>${escapeHtml(t("local.col_context"))}</th>
              <th>${escapeHtml(t("local.col_caps"))}</th>
              <th class="th-actions">${escapeHtml(t("local.col_enabled"))}</th>
            </tr></thead>
            <tbody>${models.map((m) => _localModelRow(machine, m)).join("")}</tbody>
          </table>
        </div>` : `<p class="muted small">${escapeHtml(t("local.no_models"))}</p>`}
    </div>`;
}

function renderLocalConnect() {
  const overview = state.local.overview;
  if (!overview) return;

  const featureOn = !!overview.feature_enabled;
  $("#local-feature-off").hidden = featureOn;
  $("#local-url-missing").hidden = !featureOn || !!overview.server_url;

  const c = overview.counts || {};
  const kpis = [
    { label: t("local.kpi_machines"), value: fmtNum(c.machines || 0) },
    { label: t("local.kpi_online"), value: fmtNum(c.online || 0) },
    { label: t("local.kpi_pending"), value: fmtNum(c.pending || 0) },
    { label: t("local.kpi_models"), value: fmtNum(c.models || 0) },
  ];
  $("#local-kpis").innerHTML = kpis.map((k) => `
    <div class="local-kpi">
      <div class="local-kpi-value">${escapeHtml(k.value)}</div>
      <div class="local-kpi-label">${escapeHtml(k.label)}</div>
    </div>`).join("");

  const s = overview.settings || {};
  $("#local-set-enabled").checked = !!s.enabled;
  $("#local-set-auto").checked = !!s.eligible_for_auto;
  $("#local-set-no-fallback").checked = !!s.no_cloud_fallback;
  $("#local-settings-form").querySelectorAll("input,button").forEach((el) => { el.disabled = !featureOn; });

  const machines = overview.machines || [];
  const host = $("#local-machines");
  host.innerHTML = machines.map(_localMachineCard).join("");
  $("#local-machines-empty").hidden = machines.length > 0;

  renderLocalEnrollments();
  renderLocalInstall();
}

function renderLocalEnrollments() {
  const host = $("#local-enrollments");
  if (!host) return;
  const rows = state.local.enrollments || [];
  if (!rows.length) {
    host.innerHTML = `<p class="muted small">${escapeHtml(t("local.no_enrollments"))}</p>`;
    return;
  }
  host.innerHTML = rows.map((e) => {
    const state_ = e.consumed_at
      ? `<span class="pill muted">${escapeHtml(t("local.enroll_used"))}</span>`
      : `<span class="pill ok">${escapeHtml(t("local.enroll_active"))}</span>`;
    return `
      <div class="local-enrollment">
        <code>${escapeHtml(e.code_prefix)}…</code>
        <span class="muted small">${escapeHtml(e.display_name || "—")}</span>
        <span class="muted small">${e.expires_at ? escapeHtml(_fmtWhen(e.expires_at)) : ""}</span>
        ${state_}
        <button type="button" class="btn btn-ghost btn-sm" data-local-del-enrollment="${escapeHtml(e.id)}">${escapeHtml(t("local.delete"))}</button>
      </div>`;
  }).join("");
}

function renderLocalInstall() {
  const overview = state.local.overview;
  if (!overview) return;
  const cmd = overview.install_command || "—";
  $("#local-install-command").textContent = cmd;
  const files = state.local.serviceFiles?.files || {};
  const kind = state.local.serviceKind;
  $("#local-service-file").textContent = files[kind] || "—";
  $$("#local-service-seg .seg-btn").forEach((b) =>
    b.classList.toggle("active", b.dataset.localService === kind));
}

function bindLocalConnect() {
  $("#local-refresh")?.addEventListener("click", async () => {
    await loadLocalConnect();
    renderLocalConnect();
  });

  $("#local-settings-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = {
      enabled: $("#local-set-enabled").checked,
      eligible_for_auto: $("#local-set-auto").checked,
      no_cloud_fallback: $("#local-set-no-fallback").checked,
    };
    setAuthStatus("#local-settings-status", "");
    try {
      await api("/api/local-connect/settings", { method: "PUT", body: JSON.stringify(body) });
      setAuthStatus("#local-settings-status", t("local.settings_saved"), "ok");
      await loadLocalConnect();
      renderLocalConnect();
    } catch (err) {
      setAuthStatus("#local-settings-status", err.message, "err");
    }
  });

  $("#local-wizard-open")?.addEventListener("click", () => openLocalWizard());
  $("#local-new-code")?.addEventListener("click", () => openLocalWizard(1));

  $("#local-copy-install")?.addEventListener("click", (e) =>
    copyToClipboard($("#local-install-command").textContent, e.currentTarget));
  $("#local-copy-service")?.addEventListener("click", (e) =>
    copyToClipboard($("#local-service-file").textContent, e.currentTarget));

  $$("#local-service-seg .seg-btn").forEach((b) =>
    b.addEventListener("click", () => {
      state.local.serviceKind = b.dataset.localService;
      renderLocalInstall();
    }));

  $("#local-machines")?.addEventListener("click", onLocalMachineAction);
  $("#local-machines")?.addEventListener("change", onLocalModelToggle);
  $("#local-enrollments")?.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-local-del-enrollment]");
    if (!btn) return;
    if (!confirm(t("local.confirm_delete_enrollment"))) return;
    try {
      await api(`/api/local-connect/enrollments/${btn.dataset.localDelEnrollment}`, { method: "DELETE" });
      await loadLocalConnect();
      renderLocalConnect();
    } catch (err) {
      toast(err.message, "err");
    }
  });

  bindLocalWizard();
}

async function onLocalMachineAction(e) {
  const btn = e.target.closest("[data-local-action]");
  if (!btn) return;
  const id = btn.dataset.id;
  const action = btn.dataset.localAction;
  btn.disabled = true;
  try {
    if (action === "approve") {
      await api(`/api/local-connect/machines/${id}/approve`, { method: "POST" });
      toast(t("local.toast_approved"), "ok");
    } else if (action === "revoke") {
      if (!confirm(t("local.confirm_revoke"))) { btn.disabled = false; return; }
      await api(`/api/local-connect/machines/${id}/revoke`, { method: "POST" });
      toast(t("local.toast_revoked"), "ok");
    } else if (action === "delete") {
      if (!confirm(t("local.confirm_delete_machine"))) { btn.disabled = false; return; }
      await api(`/api/local-connect/machines/${id}`, { method: "DELETE" });
      toast(t("local.toast_deleted"), "ok");
    } else if (action === "rotate") {
      if (!confirm(t("local.confirm_rotate"))) { btn.disabled = false; return; }
      const r = await api(`/api/local-connect/machines/${id}/rotate`, { method: "POST" });
      showLocalCredential(r.credential);
    } else if (action === "discover") {
      await api(`/api/local-connect/machines/${id}/discover`, { method: "POST" });
      toast(t("local.toast_discovered"), "ok");
    }
    await loadLocalConnect();
    renderLocalConnect();
  } catch (err) {
    toast(err.message, "err");
    btn.disabled = false;
  }
}

async function onLocalModelToggle(e) {
  const input = e.target.closest("[data-local-toggle-model]");
  if (!input) return;
  const modelPk = input.dataset.localToggleModel;
  const machineId = input.dataset.machine;
  input.disabled = true;
  try {
    await api(`/api/local-connect/machines/${machineId}/models/${modelPk}`, {
      method: "PATCH",
      body: JSON.stringify({ is_enabled: input.checked }),
    });
    await loadLocalConnect();
    renderLocalConnect();
  } catch (err) {
    input.checked = !input.checked;
    input.disabled = false;
    toast(err.message, "err");
  }
}

function showLocalCredential(credential) {
  const dlg = $("#local-wizard");
  const body = $("#local-step-body");
  const steps = $("#local-steps");
  if (steps) steps.innerHTML = "";
  if (body) {
    body.innerHTML = `
      <p class="callout callout-warn">
        <span class="callout-head">${escapeHtml(t("local.credential_once_title"))}</span>
        <span>${escapeHtml(t("local.credential_once_body"))}</span>
      </p>
      <pre class="code-pre"><code>${escapeHtml(credential)}</code></pre>`;
  }
  $("#local-wizard-back").hidden = true;
  state.local.credentialOnly = true;
  const next = $("#local-wizard-next");
  next.hidden = false;
  next.textContent = t("local.wizard_done");
  dlg.showModal();
}

/* ── wizard ─────────────────────────────────────────────────────────────── */

function _localDerivedStep(overview) {
  if (!overview?.feature_enabled) return 0;
  const machines = overview.machines || [];
  const live = machines.filter((m) => m.status !== "revoked");
  const approved = live.filter((m) => m.status === "approved");
  const enabledModels = approved.reduce(
    (n, m) => n + (m.models || []).filter((x) => x.is_enabled).length, 0);
  if (!live.length) return state.local.enrollments.length ? 2 : 1;
  if (!approved.length) return 6;
  if (!enabledModels) return 7;
  return 7;
}

function openLocalWizard(step) {
  const dlg = $("#local-wizard");
  if (!dlg) return;
  state.local.wizardStep = typeof step === "number"
    ? step : _localDerivedStep(state.local.overview);
  state.local.wizardCode = null;
  renderLocalWizard();
  if (!dlg.open) dlg.showModal();
}

function _localWizardBody(step) {
  const overview = state.local.overview || {};
  const serverUrl = overview.server_url || "https://your-geekcubo-host";
  const install = overview.install_command || "";
  const code = state.local.wizardCode?.code || "<ENROLLMENT_CODE>";
  const enroll = `python -m geekcubo_connector enroll --server ${serverUrl} --code ${code}`;
  const run = `geekcubo-connector run --server ${serverUrl}`;
  const machine = (overview.machines || []).find((m) => m.status !== "revoked");

  switch (step) {
    case 0:
      return `
        <h3>${escapeHtml(t("local.w0_title"))}</h3>
        <p class="muted">${escapeHtml(t("local.w0_body"))}</p>
        ${overview.feature_enabled ? `<p class="callout callout-info">${escapeHtml(t("local.w0_ready"))}</p>`
          : `<p class="callout callout-warn">${escapeHtml(t("local.w0_blocked"))}</p>`}`;
    case 1:
      return `
        <h3>${escapeHtml(t("local.w1_title"))}</h3>
        <p class="muted">${escapeHtml(t("local.w1_body"))}</p>
        <label class="field"><span class="field-label">${escapeHtml(t("local.w1_name"))}</span>
          <input id="local-wizard-name" maxlength="120" autocomplete="off" placeholder="${escapeHtml(t("local.w1_name_ph"))}" value="${escapeHtml(state.local.wizardName || "")}">
          <span class="field-help">${escapeHtml(t("local.w1_name_help"))}</span>
        </label>
        ${state.local.wizardCode ? `
          <p class="callout callout-info">
            <span class="callout-head">${escapeHtml(t("local.w1_created"))}</span>
            <code class="local-code">${escapeHtml(state.local.wizardCode.code)}</code>
          </p>` : ""}`;
    case 2:
      return `
        <h3>${escapeHtml(t("local.w2_title"))}</h3>
        <p class="muted">${escapeHtml(t("local.w2_body"))}</p>
        <pre class="code-pre"><code>${escapeHtml(install.replace("<ENROLLMENT_CODE>", code))}</code></pre>
        <p class="muted small">${escapeHtml(t("local.w2_note"))}</p>`;
    case 3:
      return `
        <h3>${escapeHtml(t("local.w3_title"))}</h3>
        <p class="muted">${escapeHtml(t("local.w3_body"))}</p>
        <pre class="code-pre"><code>${escapeHtml(enroll)}</code></pre>
        <p class="muted small">${escapeHtml(t("local.w3_note"))}</p>`;
    case 4:
      return `
        <h3>${escapeHtml(t("local.w4_title"))}</h3>
        <p class="muted">${escapeHtml(t("local.w4_body"))}</p>
        <pre class="code-pre"><code>${escapeHtml(run)}</code></pre>
        <p class="muted small">${escapeHtml(t("local.w4_note"))}</p>`;
    case 5:
      return `
        <h3>${escapeHtml(t("local.w5_title"))}</h3>
        <p class="muted">${escapeHtml(t("local.w5_body"))}</p>
        ${machine
          ? `<p class="callout callout-info">${escapeHtml(tf("local.w5_seen", { name: machine.display_name || machine.id }))}</p>`
          : `<p class="callout callout-warn">${escapeHtml(t("local.w5_waiting"))}</p>`}
        <button type="button" class="btn btn-ghost btn-sm" id="local-wizard-recheck">${escapeHtml(t("local.w5_recheck"))}</button>`;
    case 6:
      return `
        <h3>${escapeHtml(t("local.w6_title"))}</h3>
        <p class="muted">${escapeHtml(t("local.w6_body"))}</p>
        ${machine
          ? `<div class="local-wizard-machine">
               <strong>${escapeHtml(machine.display_name || machine.id)}</strong>
               ${_localMachineStatusPill(machine)}
               ${machine.status === "pending"
                 ? `<button type="button" class="btn btn-primary btn-sm" data-local-action="approve" data-id="${escapeHtml(machine.id)}">${escapeHtml(t("local.action_approve"))}</button>`
                 : `<span class="pill ok">${escapeHtml(t("local.status_approved"))}</span>`}
             </div>`
          : `<p class="callout callout-warn">${escapeHtml(t("local.w6_none"))}</p>`}`;
    case 7:
      return `
        <h3>${escapeHtml(t("local.w7_title"))}</h3>
        <p class="muted">${escapeHtml(t("local.w7_body"))}</p>
        <p class="callout callout-info">${escapeHtml(t("local.w7_done"))}</p>
        <button type="button" class="btn btn-ghost btn-sm" data-local-wizard-close>${escapeHtml(t("local.wizard_close"))}</button>`;
    default:
      return "";
  }
}

const LOCAL_STEP_KEYS = [
  "local.step1", "local.step2", "local.step3", "local.step4",
  "local.step5", "local.step6", "local.step7", "local.step8",
];

function renderLocalWizard() {
  const step = state.local.wizardStep;
  state.local.credentialOnly = false;
  const stepsEl = $("#local-steps");
  if (stepsEl) {
    stepsEl.innerHTML = LOCAL_STEP_KEYS.map((k, i) => {
      const cls = i < step ? "done" : i === step ? "active" : "";
      return `<li class="local-step ${cls}"><span class="local-step-num">${i + 1}</span><span class="local-step-label">${escapeHtml(t(k))}</span></li>`;
    }).join("");
  }
  const body = $("#local-step-body");
  if (body) body.innerHTML = _localWizardBody(step);

  const back = $("#local-wizard-back");
  back.hidden = step === 0;
  back.disabled = step === 0;
  back.textContent = t("local.wizard_back");

  const next = $("#local-wizard-next");
  next.hidden = false;
  next.textContent = step === LOCAL_WIZARD_STEPS - 1 ? t("local.wizard_done") : t("local.wizard_next");

  const err = $("#local-wizard-error");
  if (err) { err.hidden = true; err.textContent = ""; }

  $("#local-wizard-recheck")?.addEventListener("click", async (e) => {
    e.currentTarget.disabled = true;
    await loadLocalConnect();
    renderLocalConnect();
    const machine = (state.local.overview?.machines || []).find((m) => m.status !== "revoked");
    if (machine) state.local.wizardStep = 6;
    renderLocalWizard();
  });

  body?.querySelectorAll("[data-local-action]").forEach((b) =>
    b.addEventListener("click", async () => {
      await onLocalMachineAction({ target: b });
      renderLocalWizard();
    }));
}

function bindLocalWizard() {
  const dlg = $("#local-wizard");
  if (!dlg) return;
  dlg.addEventListener("click", (e) => {
    if (e.target.closest("[data-local-wizard-close]")) dlg.close();
  });

  $("#local-wizard-back")?.addEventListener("click", () => {
    if (state.local.wizardStep > 0) {
      state.local.wizardStep -= 1;
      renderLocalWizard();
    }
  });

  $("#local-wizard-next")?.addEventListener("click", async () => {
    const step = state.local.wizardStep;
    const err = $("#local-wizard-error");
    const fail = (msg) => {
      if (err) { err.hidden = false; err.textContent = msg; }
      toast(msg, "err");
    };
    if (state.local.credentialOnly) {
      state.local.credentialOnly = false;
      dlg.close();
      return;
    }
    try {
      if (step === 0) {
        if (!state.local.overview?.feature_enabled) {
          fail(t("local.w0_blocked"));
          return;
        }
      } else if (step === 1) {
        if (!state.local.wizardCode) {
          const name = $("#local-wizard-name")?.value?.trim() || undefined;
          state.local.wizardName = name || "";
          const r = await api("/api/local-connect/enrollments", {
            method: "POST",
            body: JSON.stringify({ display_name: name }),
          });
          state.local.wizardCode = r;
          await loadLocalConnect();
          renderLocalConnect();
          renderLocalWizard();
          return;
        }
      } else if (step === 6) {
        const machine = (state.local.overview?.machines || []).find((m) => m.status !== "revoked");
        if (machine && machine.status === "pending") {
          fail(t("local.w6_must_approve"));
          return;
        }
      }

      if (step >= LOCAL_WIZARD_STEPS - 1) {
        dlg.close();
        await loadLocalConnect();
        renderLocalConnect();
        return;
      }
      state.local.wizardStep = step + 1;
      renderLocalWizard();
    } catch (e) {
      fail(e.message);
    }
  });
}
