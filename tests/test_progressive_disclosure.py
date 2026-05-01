"""Tests for progressive disclosure UI rework.

Validates: sidebar with collapsible toggle, direct action buttons,
separate export buttons, PDF modal, flat settings layout,
collapsible panels, auto-hide empty panels, contextual actions.
"""
import re


# ── SIDEBAR LAYOUT ───────────────────────────────────────────────────────────

class TestSidebarLayout:
    """Sidebar should have Views + Actions sections with direct buttons."""

    def test_sidebar_has_collapse_toggle(self, client):
        html = client.get("/").data.decode()
        assert "sidebar-toggle" in html
        assert "toggleSidebar()" in html

    def test_sidebar_has_views_label(self, client):
        html = client.get("/").data.decode()
        assert ">Views<" in html

    def test_sidebar_has_actions_label(self, client):
        html = client.get("/").data.decode()
        assert ">Actions<" in html

    def test_sidebar_has_add_transaction(self, client):
        html = client.get("/").data.decode()
        assert "openAddModal()" in html
        assert "Add Transaction" in html

    def test_sidebar_has_transfer(self, client):
        html = client.get("/").data.decode()
        assert "openTransferModal()" in html
        assert "Transfer" in html

    def test_sidebar_has_export_month(self, client):
        html = client.get("/").data.decode()
        assert "exportCSV(false)" in html
        assert "Export Month" in html

    def test_sidebar_has_export_all(self, client):
        html = client.get("/").data.decode()
        assert "exportCSV(true)" in html
        assert "Export All" in html

    def test_sidebar_has_export_pdf(self, client):
        html = client.get("/").data.decode()
        assert "openPdfModal()" in html
        assert "Export PDF" in html

    def test_views_still_present(self, client):
        html = client.get("/").data.decode()
        assert "Dashboard" in html
        assert "Transactions" in html
        assert "Year Review" in html
        assert "Import CSV" in html
        assert "Settings" in html

    def test_nav_icons_wrapped(self, client):
        html = client.get("/").data.decode()
        assert "nav-icon" in html
        assert "nav-label-text" in html

    def test_data_tips_for_collapsed_mode(self, client):
        html = client.get("/").data.decode()
        assert 'data-tip="Dashboard"' in html
        assert 'data-tip="Settings"' in html


class TestSidebarCSS:
    """CSS for collapsible sidebar."""

    def test_sidebar_toggle_styles(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".sidebar-toggle" in css

    def test_collapsed_sidebar_width(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".sidebar.collapsed" in css
        assert "--sidebar-w-col" in css

    def test_collapsed_hides_labels(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".sidebar.collapsed .nav-label-text" in css

    def test_nav_icon_styles(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".nav-icon" in css

    def test_sidebar_bottom_styles(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".sidebar-bottom-row" in css
        assert ".sidebar-bottom-label" in css


# ── PDF MODAL ────────────────────────────────────────────────────────────────

class TestPdfModal:
    """PDF export modal should work correctly."""

    def test_pdf_modal_exists(self, client):
        html = client.get("/").data.decode()
        assert 'id="pdf-modal"' in html

    def test_pdf_include_transactions_checkbox(self, client):
        html = client.get("/").data.decode()
        assert 'id="pdf-include-txns"' in html

    def test_export_pdf_function(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function exportPdf" in js

    def test_open_pdf_modal_function(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function openPdfModal" in js

    def test_csv_export_function(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function exportCSV" in js


# ── SETTINGS LAYOUT ─────────────────────────────────────────────────────────

class TestSettingsLayout:
    """Settings page should have a flat, scrollable layout."""

    def test_dashboard_layout_section(self, client):
        html = client.get("/").data.decode()
        assert "Dashboard Layout" in html

    def test_categories_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="sec-settings"' in html
        settings_start = html.index('id="sec-settings"')
        settings_section = html[settings_start:]
        assert "Categories" in settings_section

    def test_budgets_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="budget-panel"' in html
        assert "Monthly Budgets" in html

    def test_goals_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="goals-panel"' in html
        assert "Savings Goals" in html

    def test_accounts_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="accounts-panel"' in html

    def test_schedules_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="schedules-panel"' in html
        assert "Scheduled Transactions" in html

    def test_groups_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="groups-panel"' in html
        assert "Category Groups" in html

    def test_learned_merchants_section(self, client):
        html = client.get("/").data.decode()
        assert "Learned Merchants" in html

    def test_import_rules_section(self, client):
        html = client.get("/").data.decode()
        assert "Import Rules" in html

    def test_show_budget_scrolls(self, client):
        js = client.get("/static/js/app.js").data.decode()
        fn_start = js.index("function showBudgetPanel")
        fn_section = js[fn_start:fn_start + 200]
        assert "scrollIntoView" in fn_section

    def test_show_goals_scrolls(self, client):
        js = client.get("/static/js/app.js").data.decode()
        fn_start = js.index("function showGoalsPanel")
        fn_section = js[fn_start:fn_start + 200]
        assert "scrollIntoView" in fn_section

    def test_show_accounts_scrolls(self, client):
        js = client.get("/static/js/app.js").data.decode()
        fn_start = js.index("function showAccountsPanel")
        fn_section = js[fn_start:fn_start + 200]
        assert "scrollIntoView" in fn_section


# ── COLLAPSIBLE PANELS + AUTO-HIDE ──────────────────────────────────────────

class TestCollapsiblePanels:
    """Dashboard panels should be collapsible by clicking the title."""

    def test_init_function_exists(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function initCollapsiblePanels" in js

    def test_collapsed_class_in_css(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".panel.panel-collapsed" in css

    def test_chevron_class_in_css(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".panel-collapse-chevron" in css

    def test_collapsed_hides_content(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert re.search(r"\.panel\.panel-collapsed\s*>\s*:not\(\.panel-title\)\s*\{[^}]*display:\s*none", css)

    def test_state_persisted_in_localstorage(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "'panelCollapsed'" in js
        assert "localStorage.setItem" in js

    def test_init_called_after_layout(self, client):
        js = client.get("/static/js/app.js").data.decode()
        layout_pos = js.index("applyDashboardLayout();")
        init_pos = js.index("initCollapsiblePanels()", layout_pos)
        assert init_pos > layout_pos

    def test_title_clickable(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert re.search(r"\.panel-title\s*\{[^}]*cursor:\s*pointer", css)

    def test_button_clicks_not_collapsed(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "e.target.closest('button')" in js


class TestAutoHideEmptyPanels:
    """Panels with no data should auto-hide."""

    def test_auto_hide_function_exists(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function autoHideEmptyPanels" in js

    def test_auto_hidden_class_in_css(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".panel-auto-hidden" in css

    def test_auto_hidden_hides_panel(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert re.search(r"\.panel-auto-hidden\s*\{[^}]*display:\s*none\s*!important", css)

    def test_called_after_render(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "await Promise.all(renderPromises)" in js
        promise_pos = js.index("await Promise.all(renderPromises)")
        auto_hide_pos = js.index("autoHideEmptyPanels()", promise_pos)
        assert auto_hide_pos > promise_pos

    def test_checks_all_panels(self, client):
        js = client.get("/static/js/app.js").data.decode()
        fn_start = js.index("function autoHideEmptyPanels")
        fn_section = js[fn_start:fn_start + 2000]
        assert "'spending-by-category'" in fn_section
        assert "'donut-chart'" in fn_section
        assert "'averages'" in fn_section
        assert "'recent-txns'" in fn_section
        assert "'recurring'" in fn_section
        assert "'spending-trends'" in fn_section
        assert "'savings-goals'" in fn_section
        assert "'net-worth'" in fn_section
        assert "'account-balances'" in fn_section

    def test_skips_user_hidden(self, client):
        js = client.get("/static/js/app.js").data.decode()
        fn_start = js.index("function autoHideEmptyPanels")
        fn_section = js[fn_start:fn_start + 500]
        assert "panel-hidden" in fn_section


# ── CONTEXTUAL ACTIONS ──────────────────────────────────────────────────────

class TestContextualActions:
    """Dashboard gear buttons should navigate to settings and scroll."""

    def test_settings_button_in_spending_by_category(self, client):
        html = client.get("/").data.decode()
        panel_start = html.index('data-panel-id="spending-by-category"')
        panel_section = html[panel_start:panel_start + 500]
        assert "showBudgetPanel()" in panel_section

    def test_settings_button_in_savings_goals(self, client):
        html = client.get("/").data.decode()
        panel_start = html.index('data-panel-id="savings-goals"')
        panel_section = html[panel_start:panel_start + 500]
        assert "showGoalsPanel()" in panel_section

    def test_settings_button_in_account_balances(self, client):
        html = client.get("/").data.decode()
        panel_start = html.index('data-panel-id="account-balances"')
        panel_section = html[panel_start:panel_start + 500]
        assert "showAccountsPanel()" in panel_section

    def test_customize_button_on_dashboard(self, client):
        html = client.get("/").data.decode()
        assert "openCustomizeModal()" in html
        assert "Customize dashboard layout" in html


# ── INTEGRATION: ALL VIEWS STILL WORK ───────────────────────────────────────

class TestViewsIntegrity:
    """All 5 main views should still be present and navigable."""

    def test_dashboard_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="sec-dashboard"' in html

    def test_transactions_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="sec-transactions"' in html

    def test_year_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="sec-year"' in html

    def test_import_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="sec-import"' in html

    def test_settings_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="sec-settings"' in html

    def test_nav_function_exists(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function nav(id)" in js

    def test_dark_mode_toggle_still_present(self, client):
        html = client.get("/").data.decode()
        assert 'id="theme-toggle"' in html
        assert "toggleTheme()" in html

    def test_all_modals_present(self, client):
        html = client.get("/").data.decode()
        assert 'id="add-modal"' in html
        assert 'id="edit-modal"' in html
        assert 'id="bulk-cat-modal"' in html
        assert 'id="pdf-modal"' in html
        assert 'id="customize-modal"' in html
        assert 'id="transfer-modal"' in html
        assert 'id="contribute-modal"' in html
        assert 'id="rule-modal"' in html
        assert 'id="template-modal"' in html


# ── CARD ACCENT BARS ────────────────────────────────────────────────────────

class TestCardAccentBars:
    """Stat cards should have colored accent bars."""

    def test_accent_bar_in_html(self, client):
        html = client.get("/").data.decode()
        assert "card-accent-bar" in html

    def test_accent_bar_css(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".card-accent-bar" in css
        assert ".card-accent-bar.green" in css
        assert ".card-accent-bar.red" in css
        assert ".card-accent-bar.blue" in css


# ── EXPORT API STILL WORKS ──────────────────────────────────────────────────

class TestExportAPIStillWorks:
    """Export APIs should still function correctly."""

    def test_csv_export_endpoint(self, client):
        from tests.conftest import seed_transaction
        seed_transaction(client)
        res = client.get("/api/export?month=2026-03")
        assert res.status_code == 200
        assert "text/csv" in res.content_type or "application/octet-stream" in res.content_type

    def test_csv_export_all(self, client):
        from tests.conftest import seed_transaction
        seed_transaction(client)
        res = client.get("/api/export?month=")
        assert res.status_code == 200
