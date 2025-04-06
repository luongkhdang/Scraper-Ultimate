# Special Scraping Techniques for Restricted Websites

This document outlines the advanced techniques implemented in our scraping system to bypass anti-bot protections, paywalls, and other access restrictions. These methods are primarily used for domains listed in the `blocked_domains` collection, which employ sophisticated defenses against automated access.

## Core Techniques

### 1. Browser Fingerprint Manipulation

Browsers have unique "fingerprints" that websites can use to identify automation:

- **Consistent Fingerprinting**: Maintains the same fingerprint values throughout a browsing session but randomizes between sessions:

  - Hardware concurrency (CPU cores)
  - Device memory
  - Screen resolution and color depth
  - Platform identification (Windows/Mac/Linux)
  - Timezone offset

- **WebDriver Detection Evasion**:
  - Removes `navigator.webdriver` flag
  - Eliminates automation-related properties like `cdc_adoQpoasnfa76pfcZLmcfl_*`
  - Overrides permission query behavior to appear more browser-like

### 2. Human-Like Behavior Simulation

- **Realistic Scrolling Patterns**:

  - Non-linear scrolling with variable speeds
  - Random pauses at content (simulating reading)
  - Occasional scrolling back up (like humans do)
  - Beta distribution for natural-feeling scroll positions

- **Mouse Movement Simulation**:

  - Multi-step movements toward targets (not instant jumps)
  - Slight randomization within clickable areas
  - Realistic timing between movement and clicks
  - Variable click delays (50-150ms)

- **Timing Randomization**:
  - Random delays between actions (0.7-2.1s before cookie consent)
  - Adaptive timing based on site complexity
  - Non-uniform pauses (longer for content consumption)

### 3. IP Address & Identity Rotation

- **Tor Integration**:

  - Circuit rotation to obtain new IP addresses
  - Specialized for high-value targets (WSJ, Bloomberg, etc.)
  - Configurable proxy settings for browser contexts

- **Adaptive Retry Mechanism**:
  - Progressive delays between attempts
  - Detection history tracking to learn from failures
  - Domain-specific retry strategies

### 4. Content Extraction Resilience

- **Multiple Extraction Strategies**:

  - DOM structure analysis for content identification
  - Fallback extraction when main selectors fail
  - Adaptive content element targeting based on site structure

- **Consent & Overlay Handling**:

  - Detects and dismisses cookie consent dialogs
  - Identifies and removes modal overlays
  - Unlocks scrolling by removing body style restrictions

- **Protection Detection**:
  - Identifies CAPTCHAs, blocks, and rate limiting
  - Records detection patterns for future strategy adjustment
  - Screenshots problematic pages for analysis

## Implementation Components

### Special Strategy Extractor

The `SpecialStrategyExtractor` class orchestrates these techniques:

- Maintains consistent fingerprints within sessions
- Tracks detection history across domains
- Implements adaptive delays and retry logic
- Handles protection measures via specialized functions

### Browser Setup Module

The `browser_setup.py` module handles:

- Creating stealth browser configurations
- Setting up device emulation based on user agents
- Applying anti-detection measures to browser contexts
- Managing resource loading priorities

### Consent Handler Module

The `consent_handler.py` module:

- Identifies and interacts with cookie consent dialogs
- Removes blocking overlays and paywalls
- Restores scrolling functionality
- Simulates natural user interactions with UI elements

### Tor Integration Module

The `tor_integration.py` module provides:

- IP rotation through Tor circuit renewal
- Domain-specific decisions on Tor usage
- Browser proxy configuration for anonymous access
- Failure handling when Tor is unavailable

## Usage Patterns

The special strategy is invoked when:

1. A domain is identified in the `blocked_domains` list
2. Standard extraction methods fail with detection patterns
3. A URL redirects to a known restricted domain
4. Content quality from standard methods is insufficient

## Ethical Considerations

These techniques are primarily used for:

- Academic and research purposes
- Data analysis and trend identification
- Personal use with appropriate rate limiting

The system respects:

- `robots.txt` directives
- Rate limiting to avoid server strain
- Content attribution requirements

## Future Enhancements

Potential improvements include:

- Machine learning for automatic adaptation to new protections
- Browser rendering analysis to detect invisible traps
- Enhanced timeout handling for heavy JavaScript sites
- Expanded device emulation profiles

---

_Note: This document is for internal use only and describes technical capabilities for legitimate research purposes._
