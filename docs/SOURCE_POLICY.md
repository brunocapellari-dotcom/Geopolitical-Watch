# Source and evidence policy

## Source classes

### News / OSINT signal
Examples: GDELT-returned publisher articles.

Observed fact: a publication was captured. The article does not automatically confirm the described event.

### Research-coded
Example: UCDP GED.

Observed fact: the event exists in the specified coded dataset/version. Dataset revisions and methodology still matter.

### Curated institutional report
Example: ReliefWeb/OCHA and information partners.

Observed fact: a curated/institutional publication was captured. The system preserves its source and date.

### Sensor signal
Example: NASA FIRMS thermal anomaly.

Observed fact: a sensor detection was captured. It must not be attributed to military activity without independent evidence.

## Current credential requirements

- UCDP: authenticated token sent in `x-ucdp-access-token`; API version is explicit in every request.
- ReliefWeb V2: pre-approved `appname` required in URL; quota constraints must be respected.
- NASA FIRMS: free MAP_KEY required; transaction limits must be respected.

## Data retention

Store raw responses when terms permit, with SHA-256, collection timestamp, source ID and request metadata. Do not copy full copyrighted article bodies into reports. Reports should use titles, metadata, short analysis and links.

## Corroboration

Independent corroboration is based on evidence providers, not merely multiple queries or collector source IDs. Two GDELT queries pointing to the same publisher do not count as two independent publishers.

## Priority score

The score is a triage mechanism. It is not:

- probability of conflict;
- probability of escalation;
- official threat level;
- expected fatalities;
- expected economic loss.
