# RSS Feed Processing System

This document explains how the RSS feed scraping system works in the Meridian application, covering both the parsing logic and workflow execution.

## Core Components

The RSS feed processing system consists of two main components:

1. **Feed Parsing (`parsers.ts`)**: Handles XML parsing and standardization
2. **Feed Workflow (`rssFeed.workflow.ts`)**: Orchestrates the entire scraping process

## Feed Parsing (parsers.ts)

### Overview

The `parseRSSFeed` function converts raw XML from RSS feeds into standardized article objects, handling various RSS formats and structures.

### Key Features

- **Format Agnostic**: Handles multiple RSS/Atom feed structures:
  - Standard RSS (`rss.channel.item`)
  - Atom (`feed.entry`)
  - RDF (`rdf:RDF.item`)
  - Single item feeds (non-array responses)

- **Data Extraction**: Extracts key article data:
  - Title
  - Link URL
  - Publication date
  - Item ID

- **Data Cleaning**: Cleanses and standardizes data with:
  - URL normalization
  - String cleaning
  - Date parsing

### Error Handling

Uses the `Result` type pattern from `neverthrow` for predictable error handling:
- `PARSE_ERROR`: XML parsing failures
- `VALIDATION_ERROR`: Schema validation failures

### Usage Example

```typescript
// Get raw XML content
const feedResult = await getRssFeedWithFetch("https://example.com/feed.xml");
if (feedResult.isErr()) {
  // Handle error
  console.error(`Failed to fetch feed: ${feedResult.error.type}`);
  return;
}

// Parse the feed
const parsedFeed = await parseRSSFeed(feedResult.value);
if (parsedFeed.isErr()) {
  // Handle parsing error
  console.error(`Failed to parse feed: ${parsedFeed.error.type}`);
  return;
}

// Use the standardized articles
const articles = parsedFeed.value;
```

## Feed Workflow (rssFeed.workflow.ts)

### Overview

The `ScrapeRssFeed` workflow class manages the entire process of discovering, fetching, and storing articles from RSS feeds.

### Tiered Frequency System

The system checks feeds at different intervals based on their importance tier:

```typescript
const tierIntervals = {
  1: 60 * 60 * 1000,     // Tier 1: Check every hour
  2: 4 * 60 * 60 * 1000, // Tier 2: Check every 4 hours
  3: 6 * 60 * 60 * 1000, // Tier 3: Check every 6 hours
  4: 24 * 60 * 60 * 1000 // Tier 4: Check every 24 hours
};
```

### Workflow Steps

1. **Source Selection**
   - Queries database for RSS sources
   - Filters based on last check time and frequency tier
   - Skips feeds that don't need checking yet

2. **Rate-Limited Processing**
   - Uses `DomainRateLimiter` to prevent overloading source websites
   - Configures limits: 10 concurrent requests, 500ms global cooldown, 2s per domain
   - Handles errors gracefully for individual feeds

3. **Feed Fetching & Parsing**
   - Fetches raw XML with randomized headers
   - Parses content with `parseRSSFeed`
   - Filters for recent articles (within one week)

4. **Database Operations**
   - Stores new articles in the database
   - Updates `lastChecked` timestamp for sources
   - Avoids duplicates with `onConflictDoNothing`

5. **Article Processing Trigger**
   - Triggers the `ProcessArticles` workflow after completion
   - Creates a chain of workflows for the entire pipeline

### Error Resilience

- **Retry Logic**: Each step has configurable retries (3 attempts with exponential backoff)
- **Graceful Failures**: Individual feed failures don't stop the entire workflow
- **Transaction Safety**: Database operations use safe transactions

### Usage

The workflow can be triggered programmatically or on a schedule:

```typescript
// Trigger manually
const result = await startRssFeedScraperWorkflow(env);
if (result.isOk()) {
  console.log(`Started workflow with ID: ${result.value.id}`);
}

// Force check all feeds regardless of schedule
const forceResult = await startRssFeedScraperWorkflow(env, { force: true });
```

## Integration Flow

1. Scheduled trigger runs hourly (Cloudflare Worker cron)
2. `ScrapeRssFeed` workflow fetches due sources
3. Each source is processed with rate limiting
4. New articles are stored in the database
5. `ProcessArticles` workflow is triggered to handle content extraction
6. Full article content is retrieved and analyzed

## Dependencies

- `fast-xml-parser`: XML parsing
- `neverthrow`: Type-safe error handling
- `zod`: Schema validation
- Cloudflare Workers: Workflow orchestration
- DrizzleORM: Database operations 