# Seed Cases

Seed cases are small manually curated records used for development and testing. They are not a complete database and should not be presented as a ranking.

## 1. Seed Case Categories

The MVP needs one or more examples in each category:

```text
official_correction
official_expression_of_concern
institution_investigation
public_discussion_only
algorithmic_signal_only
no_known_event_control
```

## 2. Initial Publicly Discussed Cases

These are candidate seed records because they were part of recent public discussion. Each must be re-verified against original sources before being used in public UI.

### Human HDAC6 senses valine abundancy to regulate DNA damage

```text
DOI: 10.1038/s41586-024-08248-5
Journal: Nature
Candidate status: institution_conclusion / publisher_editor_note
Use: official handling and event timeline test
```

### Targeted activation of ferroptosis in colorectal cancer via LGR4 targeting overcomes acquired drug resistance

```text
DOI: 10.1038/s43018-023-00715-8
Journal: Nature Cancer
Candidate status: institution_investigation / public_discussion
Use: investigation notice and public discussion test
```

### Chromosomal translocation-derived aberrant Rab22a drives metastasis of osteosarcoma

```text
DOI: 10.1038/s41556-020-0522-z
Journal: Nature Cell Biology
Candidate status: official_correction / publisher_editor_note
Use: correction history test
```

### THY1+ cancer stem cells drive metastasis through a pseudohypoxic state shaped by neutrophil-derived mitochondria

```text
DOI: 10.1038/s41556-026-01876-1
Journal: Nature Cell Biology
Candidate status: public_discussion
Use: public discussion and evidence pointer test
```

### Viral glycoprotein-mimicking peptide-functionalized micelles promote drug delivery to diseased chondrocytes for osteoarthritis alleviation

```text
DOI: 10.1038/s41565-025-02082-0
Journal: Nature Nanotechnology
Candidate status: institution_investigation / public_discussion
Use: numeric signal narrative test
```

## 3. Required Fields Before Public Use

For each seed case:

- DOI verified through DOI resolver.
- Publisher landing page URL.
- OpenAlex ID if available.
- Crossref metadata.
- Exact source URLs for events.
- Neutral claim summary.
- Event date.
- Verification status.

## 4. Seed JSON Shape

```json
{
  "papers": [
    {
      "doi": "10.1038/s41586-024-08248-5",
      "expected_events": [
        {
          "event_type": "publisher_notice",
          "status_level": "publisher_notice",
          "source_url": "https://www.nature.com/articles/s41586-024-08248-5",
          "claim_summary": "Publisher page contains an editor note or related notice."
        }
      ]
    }
  ]
}
```

## 5. Control Records

Add at least two control records:

- A China-affiliated paper with no known public integrity event.
- A non-China-affiliated paper with a correction, to verify country filters.

