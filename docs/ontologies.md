# Ontology Models

`semantic-sugar` ships with pre-defined models for:

- [RDFS](https://www.w3.org/TR/rdf-schema/)
- [OWL](https://www.w3.org/OWL/)
- [Data Catalog Vocabulary (DCAT)](https://www.w3.org/ns/dcat)
- [Sensor, Observation, Sample and Actuator (SOSA)](https://www.w3.org/TR/vocab-ssn-2023/)

# Usage

Import them from `semantic_sugar.ontologies.dcat`:

```python
from semantic_sugar.ontologies.dcat import (
    Catalog,
    Dataset,
    Distribution,
    DataService,
)
```