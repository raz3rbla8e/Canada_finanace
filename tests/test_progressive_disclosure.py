"""Tests for progressive disclosure UI rework.

Validates: sidebar quick-actions popover, unified export modal,
settings tabs, collapsible panels, auto-hide empty panels,
contextual action buttons.
"""
import re


# ── PHASE 1: SIDEBAR + EXPORT CONSOLIDATION ──────────────────────────────────

class TestSidebarQuickActions:
    """Sidebar should have Quick Actions popover instead of 5 action buttons."""

    def test_quick_actions_button_exists(self, client):
        html = client.get("/").data.decode()
        assert "Quick Actions" in html
        assert "quick-actions-wrap" in html

    def test_quick_actions_popover_exists(self, client):
        html = client.get("/").data.decode()
        assert 'id="quick-actions-popover"' in html
        assert "quick-actions-popover" in html

    def test_popover_contains_add_transaction(self, client):
        html = client.get("/").data.decode()
        assert "quick-action-item" in html
        assert "openAddModal()" in html

    def test_popover_contains_transfer(self, client):
        html = client.get("/").data.decode()
        assert "openTransferModal()" in html

    def test_popover_contains_export(self, client):
        html = client.get("/").data.decode()
        assert "openExportModal()" in html

    def test_no_separate_export_month_button(self, client):
        """The old 'Export Month' sidebar button should be gone."""
        html = client.get("/").data.decode()
        assert "Export Month" not in html

    def test_no_separate_export_all_button(self, client):
        """The old 'Export All' sidebar button should be gone."""
        html = client.get("/").data.decode()
        assert "Export All" not in html

    def test_no_separate_export_pdf_button(self, client):
        """The old 'Export PDF' sidebar button should be gone."""
        html = client.get("/").data.decode()
        assert "Export PDF" not in html

    def test_no_old_actions_label(self, client):
        """The old 'Actions' nav-label should be removed."""
        html = client.get("/").data.decode()
        # Should not have a nav-label that says Actions
        assert '>Actions<' not in html

    def test_views_still_present(self, client):
        """All 5 navigation views should still be present."""
        html = client.get("/").data.decode()
        assert "Dashboard" in html
        assert "Transactions" in html
        assert "Year Review" in html
        assert "Import CSV" in html
        assert "Settings" in html

    def test_toggle_function_exists(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function toggleQuickActions" in js

    def test_close_function_exists(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function closeQuickActions" in js

    def test_click_outside_closes(self, client):
        """Document click listener should close the popover."""
        js = client.get("/static/js/app.js").data.decode()
        assert "quick-actions-wrap" in js
        assert "classList.remove('open')" in js


class TestQuickActionsCSS:
    """CSS for quick actions popover."""

    def test_popover_styles_exist(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".quick-actions-popover" in css

    def test_popover_hidden_by_default(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert re.search(r"\.quick-actions-popover\s*\{[^}]*display:\s*none", css)

    def test_popover_shown_when_open(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert re.search(r"\.quick-actions-wrap\.open\s+\.quick-actions-popover\s*\{[^}]*display:\s*block", css)

    def test_quick_action_item_styles(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".quick-action-item" in css

    def test_chevron_rotation(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert "quick-actions-chevron" in css


class TestExportModal:
    """Unified export modal replaces the old PDF modal."""

    def test_export_modal_exists(self, client):
        html = client.get("/").data.decode()
        assert 'id="export-modal"' in html

    def test_no_old_pdf_modal(self, client):
        """The old pdf-modal should be gone."""
        html = client.get("/").data.decode()
        assert 'id="pdf-modal"' not in html

    def test_format_radio_csv(self, client):
        html = client.get("/").data.decode()
        assert 'name="export-format"' in html
        assert 'value="csv"' in html

    def test_format_radio_pdf(self, client):
        html = client.get("/").data.decode()
        assert 'value="pdf"' in html

    def test_scope_radio_month(self, client):
        html = client.get("/").data.decode()
        assert 'name="export-scope"' in html
        assert 'value="month"' in html

    def test_scope_radio_all(self, client):
        html = client.get("/").data.decode()
        assert 'value="all"' in html
        assert 'id="export-scope-all"' in html

    def test_include_transactions_checkbox(self, client):
        html = client.get("/").data.decode()
        assert 'id="export-include-txns"' in html

    def test_pdf_options_hidden_by_default(self, client):
        html = client.get("/").data.decode()
        assert 'id="export-pdf-options"' in html
        assert 'display:none' in html

    def test_do_export_function(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function doExport()" in js

    def test_open_export_modal_function(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function openExportModal" in js

    def test_export_format_change_handler(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function onExportFormatChange" in js

    def test_csv_export_still_works(self, client):
        """The exportCSV function should still exist for internal use."""
        js = client.get("/static/js/app.js").data.decode()
        assert "function exportCSV" in js

    def test_export_pdf_still_works(self, client):
        """The exportPdf function should still exist for internal use."""
        js = client.get("/static/js/app.js").data.decode()
        assert "function exportPdf" in js


# ── PHASE 2: SETTINGS TABS ──────────────────────────────────────────────────

class TestSettingsTabs:
    """Settings page should use tabs instead of one long scroll."""

    def test_tab_bar_exists(self, client):
        html = client.get("/").data.decode()
        assert "settings-tabs" in html

    def test_general_tab(self, client):
        html = client.get("/").data.decode()
        assert 'data-settings-tab="general"' in html

    def test_categories_tab(self, client):
        html = client.get("/").data.decode()
        assert 'data-settings-tab="categories"' in html

    def test_accounts_tab(self, client):
        html = client.get("/").data.decode()
        assert 'data-settings-tab="accounts"' in html

    def test_import_tab(self, client):
        html = client.get("/").data.decode()
        assert 'data-settings-tab="import"' in html

    def test_general_pane(self, client):
        html = client.get("/").data.decode()
        assert 'data-tab="general"' in html

    def test_categories_pane(self, client):
        html = client.get("/").data.decode()
        assert 'data-tab="categories"' in html

    def test_accounts_pane(self, client):
        html = client.get("/").data.decode()
        assert 'data-tab="accounts"' in html

    def test_import_pane(self, client):
        html = client.get("/").data.decode()
        assert 'data-tab="import"' in html

    def test_general_is_active_by_default(self, client):
        html = client.get("/").data.decode()
        # The general tab button should be active
        assert re.search(r'settings-tab active.*data-settings-tab="general"', html)

    def test_general_pane_is_active_by_default(self, client):
        html = client.get("/").data.decode()
        assert re.search(r'settings-tab-pane active.*data-tab="general"', html)

    def test_dashboard_layout_in_general(self, client):
        """Dashboard Layout section should be inside the general tab pane."""
        html = client.get("/").data.decode()
        # Find the general pane, check Dashboard Layout is inside
        gen_start = html.index('data-tab="general"')
        gen_end = html.index('data-tab="categories"')
        general_section = html[gen_start:gen_end]
        assert "Dashboard Layout" in general_section

    def test_categories_in_categories_tab(self, client):
        html = client.get("/").data.decode()
        cat_start = html.index('data-tab="categories"')
        cat_end = html.index('data-tab="accounts"')
        cat_section = html[cat_start:cat_end]
        assert "Categories" in cat_section
        assert "Monthly Budgets" in cat_section
        assert "Category Groups" in cat_section

    def test_accounts_in_accounts_tab(self, client):
        html = client.get("/").data.decode()
        acct_start = html.index('data-tab="accounts"')
        acct_end = html.index('data-tab="import"')
        acct_section = html[acct_start:acct_end]
        assert "Accounts" in acct_section
        assert "Scheduled Transactions" in acct_section
        assert "Savings Goals" in acct_section

    def test_import_in_import_tab(self, client):
        html = client.get("/").data.decode()
        imp_start = html.index('data-tab="import"')
        import_section = html[imp_start:]
        assert "Learned Merchants" in import_section
        assert "Import Rules" in import_section


class TestSettingsTabsCSS:
    """CSS for settings tabs."""

    def test_tab_styles(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".settings-tabs" in css
        assert ".settings-tab" in css

    def test_tab_pane_hidden_by_default(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert re.search(r"\.settings-tab-pane\s*\{[^}]*display:\s*none", css)

    def test_active_tab_pane_visible(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert re.search(r"\.settings-tab-pane\.active\s*\{[^}]*display:\s*block", css)

    def test_active_tab_accent_color(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert re.search(r"\.settings-tab\.active\s*\{[^}]*color:\s*var\(--accent\)", css)


class TestSettingsTabsJS:
    """JS for settings tab switching."""

    def test_switch_function(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function switchSettingsTab" in js

    def test_tab_state_persisted(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "localStorage.setItem('settingsTab'" in js

    def test_tab_state_restored(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "localStorage.getItem('settingsTab')" in js

    def test_show_budget_switches_tab(self, client):
        js = client.get("/static/js/app.js").data.decode()
        # showBudgetPanel should switch to categories tab
        budget_fn = js[js.index("function showBudgetPanel"):js.index("function showBudgetPanel") + 200]
        assert "switchSettingsTab('categories')" in budget_fn

    def test_show_goals_switches_tab(self, client):
        js = client.get("/static/js/app.js").data.decode()
        goals_fn = js[js.index("function showGoalsPanel"):js.index("function showGoalsPanel") + 200]
        assert "switchSettingsTab('accounts')" in goals_fn

    def test_show_accounts_switches_tab(self, client):
        js = client.get("/static/js/app.js").data.decode()
        acct_fn = js[js.index("function showAccountsPanel"):js.index("function showAccountsPanel") + 200]
        assert "switchSettingsTab('accounts')" in acct_fn


# ── PHASE 3: COLLAPSIBLE PANELS + AUTO-HIDE ─────────────────────────────────

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
        """initCollapsiblePanels should be called after applyDashboardLayout."""
        js = client.get("/static/js/app.js").data.decode()
        layout_pos = js.index("applyDashboardLayout();")
        # Find the next initCollapsiblePanels call after the first applyDashboardLayout
        init_pos = js.index("initCollapsiblePanels()", layout_pos)
        assert init_pos > layout_pos

    def test_title_clickable(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert re.search(r"\.panel-title\s*\{[^}]*cursor:\s*pointer", css)

    def test_button_clicks_not_collapsed(self, client):
        """Clicking buttons inside panel-title should not collapse."""
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
        """autoHideEmptyPanels should be called after renderMonth panels complete."""
        js = client.get("/static/js/app.js").data.decode()
        assert "await Promise.all(renderPromises)" in js
        # autoHideEmptyPanels should be right after the await
        promise_pos = js.index("await Promise.all(renderPromises)")
        auto_hide_pos = js.index("autoHideEmptyPanels()", promise_pos)
        assert auto_hide_pos > promise_pos

    def test_checks_all_panels(self, client):
        """Should check each panel type for meaningful data."""
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
        """Auto-hide should skip panels already hidden by user (panel-hidden)."""
        js = client.get("/static/js/app.js").data.decode()
        fn_start = js.index("function autoHideEmptyPanels")
        fn_section = js[fn_start:fn_start + 500]
        assert "panel-hidden" in fn_section


# ── PHASE 4: CONTEXTUAL ACTIONS ─────────────────────────────────────────────

class TestContextualActions:
    """Transfer and Export should be available in context."""

    def test_transfer_button_in_account_balances(self, client):
        """Account Balances panel should have a Transfer button."""
        html = client.get("/").data.decode()
        # Find the account-balances panel section
        panel_start = html.index('data-panel-id="account-balances"')
        panel_section = html[panel_start:panel_start + 500]
        assert "openTransferModal()" in panel_section
        assert "⇄" in panel_section

    def test_settings_button_still_in_account_balances(self, client):
        """The ⚙ settings button should still be present."""
        html = client.get("/").data.decode()
        panel_start = html.index('data-panel-id="account-balances"')
        panel_section = html[panel_start:panel_start + 500]
        assert "showAccountsPanel()" in panel_section

    def test_month_menu_exists(self, client):
        """Dashboard month header should have a '...' menu."""
        html = client.get("/").data.decode()
        assert "month-menu-wrap" in html
        assert 'id="month-menu-dropdown"' in html

    def test_month_menu_has_export_options(self, client):
        html = client.get("/").data.decode()
        menu_start = html.index('id="month-menu-dropdown"')
        menu_section = html[menu_start:menu_start + 500]
        assert "Export this month" in menu_section
        assert "Export all" in menu_section

    def test_year_review_export_button(self, client):
        """Year Review section should have an export button."""
        html = client.get("/").data.decode()
        year_start = html.index('id="sec-year"')
        year_header = html[year_start:year_start + 800]
        assert "openExportModal()" in year_header

    def test_month_menu_toggle_function(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function toggleMonthMenu" in js

    def test_month_menu_close_function(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function closeMonthMenu" in js

    def test_month_menu_css(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".month-menu-dropdown" in css
        assert ".month-menu-wrap" in css


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
        assert 'id="export-modal"' in html
        assert 'id="customize-modal"' in html
        assert 'id="transfer-modal"' in html
        assert 'id="contribute-modal"' in html
        assert 'id="rule-modal"' in html
        assert 'id="template-modal"' in html


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
