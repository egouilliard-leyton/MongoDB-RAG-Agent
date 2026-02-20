*** Settings ***
Documentation     UI Smoke Test Suite - Dashboard & App Load Verification
...               Validates that the app loads correctly and Dashboard page renders content (not blank).
...               Uses semantic locators for stable, maintainable tests.

Library           Browser
Library           Collections
Library           String

Suite Setup       Open Browser To App
Suite Teardown    Close Browser

Test Tags         smoke    ui


*** Variables ***
${BASE_URL}               http://127.0.0.1:5173
${BROWSER}                chromium
${HEADLESS}               true
${TIMEOUT}                30s
${SCREENSHOT_DIR}         ${CURDIR}/../artifacts/robot


*** Test Cases ***
App Loads And Main Layout Renders
    [Documentation]    Verify the application loads successfully and displays the main Q&A System heading.
    [Tags]    critical    load
    
    # Verify page title or main heading
    Wait For Elements State    text=Q&A System    visible    timeout=${TIMEOUT}
    
    # Verify main navigation tabs are present
    Wait For Elements State    role=button >> text=Q&A    visible
    Wait For Elements State    role=button >> text=Documents    visible
    Wait For Elements State    role=button >> text=Ingestion    visible
    Wait For Elements State    role=button >> text=Dashboard    visible
    
    # Take screenshot of initial load
    Take Screenshot    ${SCREENSHOT_DIR}/01_app_loaded.png

Dashboard Tab Is Clickable
    [Documentation]    Verify Dashboard tab can be clicked and navigated to.
    [Tags]    navigation    dashboard
    
    # Click Dashboard tab using semantic locator
    Click    role=button >> text=Dashboard
    
    # Wait for navigation/content to settle
    Sleep    1s
    
    # Verify we're on Dashboard view
    Wait For Elements State    text=Dashboard    visible    timeout=${TIMEOUT}
    
    # Take screenshot after navigation
    Take Screenshot    ${SCREENSHOT_DIR}/02_dashboard_clicked.png

Dashboard Page Is Not Blank
    [Documentation]    Critical assertion: Dashboard page must render visible content, not a blank page.
    ...               Checks for h1 Dashboard heading and verifies main content area has visible elements.
    [Tags]    critical    dashboard    not-blank
    
    # Ensure we're on Dashboard (click again to be safe)
    Click    role=button >> text=Dashboard
    Sleep    2s    # Allow async data loading
    
    # Check 1: h1 "Dashboard" heading must exist
    ${heading_count}=    Get Element Count    h1:text("Dashboard")
    Should Be True    ${heading_count} >= 1    Dashboard h1 heading not found
    
    # Check 2: Main content area exists and is not empty
    ${main_exists}=    Get Element Count    main
    Should Be True    ${main_exists} >= 1    Main element not found
    
    # Check 3: Verify visible content in main (at least some text elements)
    ${visible_content}=    Evaluate Dashboard Content Visibility
    Should Be True    ${visible_content}[has_content]    Dashboard appears blank - no visible content in main area
    
    # Check 4: Look for expected Dashboard elements (any one of these indicates content)
    ${has_cards_or_loading}=    Check For Dashboard Elements
    Should Be True    ${has_cards_or_loading}    Dashboard missing expected elements (cards, charts, or loading state)
    
    # Take screenshot of Dashboard content
    Take Screenshot    ${SCREENSHOT_DIR}/03_dashboard_content.png
    
    # Log content check results
    Log    Dashboard content check: has_content=${visible_content}[has_content], text_count=${visible_content}[text_count]

Dashboard Shows Summary Cards Or Loading State
    [Documentation]    Verify Dashboard shows either summary cards (when data loaded) or loading indicator.
    [Tags]    dashboard    content
    
    # Look for summary card titles or loading indicator
    ${has_projects}=    Get Element Count    text=Total Projects
    ${has_sessions}=    Get Element Count    text=Total Sessions
    ${has_qa_pairs}=    Get Element Count    text=Q&A Pairs
    ${has_success_rate}=    Get Element Count    text=Success Rate
    ${has_loading}=    Get Element Count    text=Loading dashboard
    
    ${total_elements}=    Evaluate    ${has_projects} + ${has_sessions} + ${has_qa_pairs} + ${has_success_rate} + ${has_loading}
    Should Be True    ${total_elements} >= 1    Dashboard shows no summary cards and no loading state
    
    # Log what was found
    Log    Found: Projects=${has_projects}, Sessions=${has_sessions}, QA Pairs=${has_qa_pairs}, Success Rate=${has_success_rate}, Loading=${has_loading}


*** Keywords ***
Open Browser To App
    [Documentation]    Open browser and navigate to the application.
    New Browser    ${BROWSER}    headless=${HEADLESS}
    New Context    viewport={'width': 1280, 'height': 720}
    New Page    ${BASE_URL}
    Set Browser Timeout    ${TIMEOUT}

Evaluate Dashboard Content Visibility
    [Documentation]    Use JavaScript to count visible text elements in main content area.
    ...               Returns dict with has_content (bool) and text_count (int).
    
    ${result}=    Evaluate JavaScript    body    
    ...    () => {
    ...        const main = document.querySelector('main');
    ...        if (!main) return { has_content: false, text_count: 0, error: 'No main element' };
    ...        
    ...        // Walk through text nodes and count visible ones
    ...        const walker = document.createTreeWalker(
    ...            main,
    ...            NodeFilter.SHOW_TEXT,
    ...            {
    ...                acceptNode: (node) => {
    ...                    const text = node.textContent.trim();
    ...                    if (!text || text.length === 0) return NodeFilter.FILTER_REJECT;
    ...                    const parent = node.parentElement;
    ...                    if (!parent) return NodeFilter.FILTER_REJECT;
    ...                    const style = window.getComputedStyle(parent);
    ...                    if (style.display === 'none' || style.visibility === 'hidden') {
    ...                        return NodeFilter.FILTER_REJECT;
    ...                    }
    ...                    return NodeFilter.FILTER_ACCEPT;
    ...                }
    ...            }
    ...        );
    ...        
    ...        let count = 0;
    ...        while (walker.nextNode() && count < 100) {
    ...            if (walker.currentNode.textContent.trim().length > 0) count++;
    ...        }
    ...        
    ...        return { has_content: count > 1, text_count: count };
    ...    }
    
    RETURN    ${result}

Check For Dashboard Elements
    [Documentation]    Check if Dashboard has expected elements (summary cards, charts, or loading state).
    
    # Check for various Dashboard elements
    ${card_count}=    Get Element Count    css=.bg-white.rounded-lg
    ${heading_count}=    Get Element Count    css=h1, h2, h3
    ${loading_count}=    Get Element Count    text=Loading
    ${chart_count}=    Get Element Count    css=[class*="chart"], [class*="Chart"]
    
    # Activity Trends section
    ${trends_count}=    Get Element Count    text=Activity Trends
    
    # Any of these indicates content is present
    ${total}=    Evaluate    ${card_count} + ${heading_count} + ${loading_count} + ${chart_count} + ${trends_count}
    
    ${has_elements}=    Evaluate    ${total} >= 2
    RETURN    ${has_elements}

Take Screenshot On Failure
    [Documentation]    Keyword to capture screenshot when a test fails.
    Run Keyword If Test Failed    Take Screenshot    ${SCREENSHOT_DIR}/FAILURE_${TEST_NAME}.png
