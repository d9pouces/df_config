from df_config.utils import is_package_present

DEBUG_TOOLBAR_PANELS = [
    "debug_toolbar.panels.versions.VersionsPanel",
    "debug_toolbar.panels.timer.TimerPanel",
    "debug_toolbar.panels.settings.SettingsPanel",
    "debug_toolbar.panels.profiling.ProfilingPanel",
    "debug_toolbar.panels.headers.HeadersPanel",
    "debug_toolbar.panels.request.RequestPanel",
    "debug_toolbar.panels.sql.SQLPanel",
    "debug_toolbar.panels.templates.TemplatesPanel",
    "debug_toolbar.panels.staticfiles.StaticFilesPanel",
    "debug_toolbar.panels.cache.CachePanel",
    "debug_toolbar.panels.signals.SignalsPanel",
    "debug_toolbar.panels.redirects.RedirectsPanel",
]


def guess_djt_panels(settings_dict):
    if not settings_dict["DEBUG"] or not settings_dict["USE_DEBUG_TOOLBAR"]:
        return []
    panels = list(DEBUG_TOOLBAR_PANELS)
    if is_package_present("djt_og"):
        panels.insert(2, "djt_og.panel.OpenGraphPanel")
    if is_package_present("djt_csp"):
        panels.insert(2, "djt_csp.panel.SecurityPanel")
    if is_package_present("djt_nvu"):
        panels.insert(2, "djt_nvu.panel.W3ValidatorPanel")
    return panels


guess_djt_panels.required_settings = ["DEBUG", "USE_DEBUG_TOOLBAR"]
