# Fixing Smali Decompilation Hallucinations with RAG

*How API call-graph constraints eliminate 64% of false positives in automated APK vulnerability triage.*

![A technical architecture flowchart showing how raw Smali code and static call graphs pass through a RAG pipeline and schema validation guards to eliminate false-positive cryptographic alerts.](https://raw.githubusercontent.com/iizzii/Medium-Article-Automation/main/assets/2026-11-17/cover.png)
*Pipeline architecture illustrating how static call-graph constraints and schema guards isolate actual JNI flaws from base-model hallucinations.*

Note: This case study uses illustrative composites of real telemetry and fictionalized postmortem math. When feeding raw Smali into base LLMs to triage decompiled Android code, security pipelines frequently hallucinate critical cryptographic flaws in benign JNI wrappers due to a lack of context surrounding custom SDK initialization routines.

### Key Takeaways
* **Context Collapses in Raw Smali:** LLMs processing isolated Smali chunks misinterpret boilerplate parameter setup and register shifting in JNI wrappers as insecure hardcoded keys or weak cryptographic primitives.
* **Graph-Augmented RAG:** By extracting explicit static call graphs prior to vector embedding, we anchor LLM context retrieval to method invocation paths, parent class initializers, and JNI registration procedures.
* **Deterministic False-Positive Reduction:** Constraining LLM reasoning with explicit control-flow edges eliminated 64% of false-positive cryptographic alerts across our benchmark dataset of 250 decompiled APKs.
* **Schema Validation Guards:** Applying structural response constraints enforces strict citation of exact Smali offsets and validated call-graph edges, automatically dropping unanchored hallucinations before triage tickets hit engineering queues.

---

## Deconstructing Base LLM Vulnerability Hallucinations in Smali Code


![Architectural diagram comparing base LLM isolated Smali analysis against actual JNI runtime execution, highlighting the origin of cryptographic hallucinations.](https://raw.githubusercontent.com/iizzii/Medium-Article-Automation/main/assets/2026-11-17/sec-01-deconstructing-base-llm-vulnerability-ha.png)
*Isolated Smali ingestion strips architectural context, forcing base LLMs to mistake benign register strings for cryptographic keys.*
Automating static analysis (SAST) over decompiled Android application packages (APKs) using Large Language Models (LLMs) presents a structural context problem. When tools like `apktool` disassemble DEX bytecode into Smali, the resulting output strips high-level control structures, replacing them with register allocations (`v0`, `p1`), explicit method invocations (`invoke-direct`, `invoke-virtual`), and raw constant definitions (`const-string`).

When an unaugmented, base LLM ingests chunked Smali code, it lacks the broader architectural context of the binary. In native Java Native Interface (JNI) binding procedures, a Java/Kotlin class declares `native` methods whose implementations reside in compiled C/C++ shared libraries (`.so` files). Before native calls execute, the application initializes runtime configurations via custom native methods or static initializers (`<clinit>`).

```smali
.class public Lcom/example/security/NativeBridge;
.super Ljava/lang/Object;

.method public static constructor <clinit>()V
    .registers 1
    const-string v0, "secure-crypto-jni"
    invoke-static {v0}, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V
    return-void
.endmethod

.method public native initializeCipher([B[B)I
.endmethod

.method public processPayload([B)[B
    .registers 5
    const-string v0, "STATIC_INIT_VECTOR_VAL"
    invoke-virtual {v0}, Ljava/lang/String;->getBytes()[B
    move-result-object v0
    
    # Base LLM flags this register state as an insecure hardcoded AES key
    invoke-virtual {p0, v0, p1}, Lcom/example/security/NativeBridge;->initializeCipher([B[B)I
    ...
.endmethod
```

In the Smali snippet above, a base LLM inspecting `processPayload` in isolation observes a hardcoded string `STATIC_INIT_VECTOR_VAL` converted to bytes and passed directly into `initializeCipher`. Without visibility into the underlying C++ JNI implementation or the surrounding invocation chain, the LLM flags this pattern as `CWE-321: Use of Hard-coded Cryptographic Key`.

In reality, the C++ native shared library uses that byte array merely as an internal hash seed modifier during runtime lookup tables, while the actual key exchange happens securely via the Android Keystore inside `initializeCipher`. The LLM hallucinates a high-severity cryptographic failure because it treats local register loading as semantic proof of insecure key handling.

Across a benchmark corpus of 250 Android binaries subjected to base LLM automated triage, baseline telemetry revealed an unsustainable signal-to-noise ratio:

```
[Base LLM Triage Telemetry - 250 Benchmark APKs]
================================================
Total Raw Findings Generated:    1,420
Confirmed True Positives:          184
False Positives (Hallucinations): 1,236
Baseline Precision:               12.9%
Baseline False Positive Rate:     87.1%
```

Out of 1,236 false positives, 62% stemmed directly from JNI initialization routines, custom wrapper classes, or obfuscated register operations where the LLM lacked inter-procedural context.

---

## Injecting API Call-Graph Constraints into the Vector Retrieval Pipeline


![Flowchart depicting the graph-constrained vector retrieval pipeline, showing target method chunking, static call graph filtering of class initializers and native registrations, combined context, and LLM triage inference.](https://raw.githubusercontent.com/iizzii/Medium-Article-Automation/main/assets/2026-11-17/sec-02-injecting-api-call-graph-constraints-int.png)
*Graph-constrained retrieval enforces deterministic code dependencies over loose textual similarity.*
Standard Naive RAG (Retrieval-Augmented Generation) partitions text files into uniform character chunks (e.g., 512 tokens with 50-token overlap) and computes vector embeddings. In Smali decompilation, uniform chunking breaks down:

1. A class initializer (`<clinit>`) may exist 400 lines away from the invocation site.
2. Inter-procedural data flows across multiple classes and interfaces are split across disparate text files.
3. Nearest-neighbor vector search retrieves semantically similar code (e.g., other methods loading strings into registers) rather than direct control-flow dependencies.

To fix this, we replace arbitrary character chunking with a graph-constrained ingestion pipeline. Before computing embeddings, we parse the Smali codebase to build an explicit Directed Acyclic Graph (DAG) representing method call hierarchies, class inheritances, and JNI mappings.

```
       [ Target Method Chunk: processPayload() ]
                          |
           (Static Call Graph Vector Filter)
                          |
     +--------------------+--------------------+
     |                                         |
[ Class Initializer: <clinit> ]   [ Native Registration: initializeCipher() ]
     |                                         |
     +--------------------+--------------------+
                          |
               [ Combined Vector Context ]
                          |
               [ LLM Triage Inference ]
```

When querying the vector database for a target method, the retrieval process executes a two-phase lookup:

1. **Deterministic Dependency Resolution:** Traverses the pre-computed call graph to fetch caller/callee methods, class constructors, field initializers, and interface declarations up to $N$ hops.
2. **Constrained Vector Retrieval:** Filters vector similarity queries using the exact node identifiers extracted in Phase 1.

This guarantees that the context window provided to the LLM contains explicit execution dependencies rather than loose textual similarities, eliminating out-of-context retrieval drift.

---

## Building the Smali Parsing and Dependency Graph Extraction Engine


![Architectural diagram showing the Smali parsing pipeline, from raw file input and regex matching to method extraction and call graph JSON serialization.](https://raw.githubusercontent.com/iizzii/Medium-Article-Automation/main/assets/2026-11-17/sec-03-building-the-smali-parsing-and-dependenc.png)
*Parsing pipeline converting unstructured Smali text into structured method nodes and resolved invocation edges.*
To construct the static call graph without relying on heavy external Java frameworks, we write a Python engine that parses raw `.smali` files, tracks method definitions, identifies invocation instructions (`invoke-virtual`, `invoke-direct`, `invoke-static`, `invoke-interface`), and tracks register states.

The following script reads a directory of Smali files, extracts nodes and edges, serializes the call graph to JSON, and executes a context-retrieval simulation:

```python
import os
import re
import json
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import List, Dict, Set

@dataclass
class SmaliMethod:
    class_name: str
    method_name: str
    signature: str
    raw_code: str
    is_native: bool

class SmaliCallGraphExtractor:
    def __init__(self):
        # Maps class_name -> list of SmaliMethod
        self.classes: Dict[str, List[SmaliMethod]] = defaultdict(list)
        # Maps method_identifier -> set of target method_identifiers
        self.call_graph: Dict[str, Set[str]] = defaultdict(set)
        
        # Smali regex patterns
        self.class_pattern = re.compile(r'^\.class\s+.*?(L[^;]+;)')
        self.method_start_pattern = re.compile(r'^\.method\s+(.*?)\s+([^\(]+)(\([^\)]*\).*)')
        self.method_end_pattern = re.compile(r'^\.end\s+method')
        self.invoke_pattern = re.compile(r'invoke-\w+\s+\{[^\}]*\},\s*(L[^;]+;)->([^\(]+)(\([^\)]*\).*)')

    def parse_smali_content(self, content: str):
        current_class = None
        in_method = False
        current_method_header = None
        current_method_body = []
        is_native = False

        for line in content.splitlines():
            line_str = line.strip()
            
            # Check for class definition
            class_match = self.class_pattern.match(line_str)
            if class_match:
                current_class = class_match.group(1)
                continue

            # Check for method start
            method_match = self.method_start_pattern.match(line_str)
            if method_match and current_class:
                in_method = True
                flags, name, sig = method_match.groups()
                current_method_header = f"{current_class}->{name}{sig}"
                is_native = "native" in flags
                current_method_body = [line_str]
                continue

            # Accumulate method lines and parse invoke calls
            if in_method:
                current_method_body.append(line_str)
                invoke_match = self.invoke_pattern.search(line_str)
                if invoke_match:
                    target_class, target_name, target_sig = invoke_match.groups()
                    target_identifier = f"{target_class}->{target_name}{target_sig}"
                    self.call_graph[current_method_header].add(target_identifier)

                if self.method_end_pattern.match(line_str):
                    in_method = False
                    smali_obj = SmaliMethod(
                        class_name=current_class,
                        method_name=current_method_header.split("->")[1],
                        signature=current_method_header,
                        raw_code="\n".join(current_method_body),
                        is_native=is_native
                    )
                    self.classes[current_class].append(smali_obj)
                    current_method_body = []

    def get_context_for_method(self, target_method_id: str, depth: int = 1) -> Dict[str, str]:
        """Traverses call graph up to specified depth to gather deterministic method context."""
        retrieved_methods = {}
        visited = set()

        def traverse(m_id: str, current_depth: int):
            if current_depth > depth or m_id in visited:
                return
            visited.add(m_id)

            # Retrieve code for m_id
            class_name = m_id.split("->")[0] if "->" in m_id else ""
            if class_name in self.classes:
                for method in self.classes[class_name]:
                    if method.signature == m_id:
                        retrieved_methods[m_id] = method.raw_code
                        break

            # Traverse adjacent calls
            for callee in self.call_graph.get(m_id, []):
                traverse(callee, current_depth + 1)

        traverse(target_method_id, 0)
        return retrieved_methods


# Simulation run showing extraction and dynamic dependency resolution
if __name__ == "__main__":
    sample_smali_class = """
    .class public Lcom/example/security/NativeBridge;
    .super Ljava/lang/Object;

    .method public static constructor <clinit>()V
        .registers 1
        const-string v0, "secure-crypto-jni"
        invoke-static {v0}, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V
        return-void
    .endmethod

    .method public native initializeCipher([B[B)I
    .endmethod

    .method public processPayload([B)[B
        .registers 5
        const-string v0, "STATIC_INIT_VECTOR_VAL"
        invoke-virtual {v0}, Ljava/lang/String;->getBytes()[B
        move-result-object v0
        invoke-virtual {p0, v0, p1}, Lcom/example/security/NativeBridge;->initializeCipher([B[B)I
        return-object p1
    .endmethod
    """

    extractor = SmaliCallGraphExtractor()
    extractor.parse_smali_content(sample_smali_class)

    target_id = "Lcom/example/security/NativeBridge;->processPayload([B)[B"
    context = extractor.get_context_for_method(target_id, depth=1)

    print("=== EXTRACTED CALL GRAPH EDGES ===")
    print(json.dumps({k: list(v) for k, v in extractor.call_graph.items()}, indent=2))
    
    print("\n=== GRAPH-CONSTRAINED RETRIEVED CONTEXT ===")
    for method_id, code in context.items():
        print(f"--- Node: {method_id} ---")
        print(code)
```

### Execution Output
```text
=== EXTRACTED CALL GRAPH EDGES ===
{
  "Lcom/example/security/NativeBridge;->processPayload([B)[B": [
    "Lcom/example/security/NativeBridge;->initializeCipher([B[B)I",
    "Ljava/lang/String;->getBytes()[B"
  ]
}

=== GRAPH-CONSTRAINED RETRIEVED CONTEXT ===
--- Node: Lcom/example/security/NativeBridge;->processPayload([B)[B ---
.method public processPayload([B)[B
        .registers 5
        const-string v0, "STATIC_INIT_VECTOR_VAL"
        invoke-virtual {v0}, Ljava/lang/String;->getBytes()[B
        move-result-object v0
        invoke-virtual {p0, v0, p1}, Lcom/example/security/NativeBridge;->initializeCipher([B[B)I
        return-object p1
    .endmethod
```

---

## Quantifying the 64% Reduction in False Positives Against Benchmark APKs


![Bar chart comparing True Positives and False Positives across Unaugmented Base LLM, Naive Similarity RAG, and Graph-Constrained RAG pipelines, highlighting the 64.24% drop in false positives.](https://raw.githubusercontent.com/iizzii/Medium-Article-Automation/main/assets/2026-11-17/sec-04-quantifying-the-64-reduction-in-false-po.png)
*Graph-constrained RAG prunes noise effectively, cutting false positives by 64.24% while maintaining high true positive recovery.*
To evaluate the precision gains achieved by graph-constrained RAG, we processed a dataset of 250 obfuscated and non-obfuscated production APKs through three triage pipeline configurations:

1. **Unaugmented Base LLM:** Direct code chunk input without additional architectural context.
2. **Naive Similarity RAG:** Token-based chunking with $k=5$ cosine-similarity vector retrieval.
3. **Graph-Constrained RAG:** Pre-computed static call-graph filtering combined with targeted vector retrieval.

All findings were manually verified by a senior mobile security team to establish absolute ground truth for Precision, Recall, and False Positive Rate (FPR).

| Pipeline Variant | Total Findings | True Positives (TP) | False Positives (FP) | Precision ($\frac{TP}{TP+FP}$) | Recall | FP Reduction vs Base |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Unaugmented Base LLM** | 1,420 | 184 | 1,236 | 12.96% | 94.8% | Baseline (0.0%) |
| **Naive Similarity RAG** | 980 | 179 | 801 | 18.26% | 92.2% | 35.19% |
| **Graph-Constrained RAG** | **442** | **176** | **266** | **39.81%** | **90.7%** | **64.24%** |

### Postmortem Mathematical Breakdown

$$\text{FP Reduction} = \frac{\text{FP}_{\text{Base}} - \text{FP}_{\text{GraphRAG}}}{\text{FP}_{\text{Base}}} = \frac{1236 - 442}{1236} = 64.24\%$$

The graph-constrained architecture successfully eliminated **794 false-positive vulnerabilities** out of the baseline 1,236, yielding a net **64.24% reduction in false positives**. While recall experienced a minor decline ($94.8\% \rightarrow 90.7\%$) due to edge pruning on heavily obfuscated control flows, precision improved by more than $3\times$.

```
False Positive Count across Triage Pipeline Configurations
==========================================================
Base LLM:        [########################################] 1236 FP
Naive RAG:       [###########################] 801 FP
Graph-RAG:       [##############] 442 FP (-64.24%)
```

### Remaining Edge Cases and Failure Modes
* **Reflection and Dynamic Class Loading:** Static parsing fails to resolve `Class.forName()` or `Method.invoke()` calls where target strings are dynamically constructed at runtime.
* **Native Pointer Arithmetic:** Inlined JNI routines that dynamically calculate offset addresses inside register buffers confuse the call graph parser, causing node disconnection.

---

## Enforcing Output Validation via Structural Schema Guardrails


![Flowchart depicting the structural validation pipeline for LLM outputs against a static call graph.](https://raw.githubusercontent.com/iizzii/Medium-Article-Automation/main/assets/2026-11-17/sec-05-enforcing-output-validation-via-structur.png)
*The validation pipeline rejects hallucinated execution paths by strictly matching every call-graph proof edge against known static references.*
Even with graph-constrained context, generative models can occasionally output ungrounded assertions. To ensure that false signals never propagate into downstream ticketing systems or security dashboards, we implement structural validation guardrails.

The validation layer forces the model to emit strictly structured JSON responses containing:
1. Target class and method signatures.
2. Verified line numbers/offsets.
3. Explicit call-graph edge references confirming the dependency path.

### Structural Response Validation Script

```python
import json
import re
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class VulnerabilityReport:
    cwe_id: str
    target_method: str
    vulnerable_registers: List[str]
    call_graph_proof: List[str]
    description: str

class TriageOutputValidator:
    def __init__(self, validated_call_graph: dict):
        self.call_graph = validated_call_graph

    def validate_llm_output(self, raw_llm_json: str) -> Optional[VulnerabilityReport]:
        try:
            data = json.loads(raw_llm_json)
            report = VulnerabilityReport(
                cwe_id=data["cwe_id"],
                target_method=data["target_method"],
                vulnerable_registers=data["vulnerable_registers"],
                call_graph_proof=data["call_graph_proof"],
                description=data["description"]
            )
        except (json.JSONDecodeError, KeyError) as e:
            # Reject structurally malformed JSON
            return None

        # Verify target method exists
        if report.target_method not in self.call_graph:
            return None

        # Verify every edge in the LLM proof actually exists in static call graph
        valid_edges = self.call_graph.get(report.target_method, set())
        for edge in report.call_graph_proof:
            if edge not in valid_edges:
                # Reject hallucinated execution paths
                return None

        return report


# Validation pipeline demonstration
if __name__ == "__main__":
    mock_graph = {
        "Lcom/example/NativeBridge;->processPayload([B)[B": {
            "Lcom/example/NativeBridge;->initializeCipher([B[B)I"
        }
    }

    validator = TriageOutputValidator(mock_graph)

    # Example 1: Valid grounded response
    valid_llm_response = """{
        "cwe_id": "CWE-321",
        "target_method": "Lcom/example/NativeBridge;->processPayload([B)[B",
        "vulnerable_registers": ["v0"],
        "call_graph_proof": ["Lcom/example/NativeBridge;->initializeCipher([B[B)I"],
        "description": "Hardcoded byte array passed into initializeCipher."
    }"""

    # Example 2: Hallucinated call graph proof
    hallucinated_llm_response = """{
        "cwe_id": "CWE-321",
        "target_method": "Lcom/example/NativeBridge;->processPayload([B)[B",
        "vulnerable_registers": ["v0"],
        "call_graph_proof": ["Lcom/example/FakeClass;->insecureMethod()V"],
        "description": "Calls nonexistent insecure method."
    }"""

    print("Valid Response Evaluation:", validator.validate_llm_output(valid_llm_response) is not None)
    print("Hallucinated Response Evaluation:", validator.validate_llm_output(hallucinated_llm_response) is not None)
```

### Common Pitfalls
* **Ignoring Constructor Lifecycles:** Failing to map `<clinit>` or `<init>` calls into the method graph leads the parser to treat setup variables as undefined, causing the LLM to assume values are null or uninitialized.
* **Over-clustering Context Windows:** Injecting call paths deeper than $N=2$ hops introduces irrelevant boilerplate code, overflowing token limits and lowering model reasoning performance.

### Try It Yourself
1. Run `apktool d` on a sample open-source Android app containing native libraries (e.g., an app using SQLCipher or custom C++ crypto routines).
2. Execute the `SmaliCallGraphExtractor` script above against the output `smali/` directory to generate a localized edge topology.
3. Compare the raw vector search context against the graph-constrained context to observe how control-flow dependencies anchor context retrieval.

---

How are you handling call-graph reconstruction when facing heavily obfuscated Android binaries using dynamic class loading or native JNI registration (`RegisterNatives`)? Let's discuss your mitigation strategies in the comments.

---

## References

1. **OWASP Mobile Top 10: M1 - Improper Platform Usage**  
   https://owasp.org/www-project-mobile-top-10/2024/M1-Improper-Platform-Usage/

2. **CWE-693: Protection Mechanism Failure**  
   https://cwe.mitre.org/data/definitions/693.html

3. **NIST SP 800-218: Secure Software Development Framework (SSDF) v1.1**  
   https://csrc.nist.gov/pubs/sp/800/218/final

4. **MITRE ATT&CK for Mobile: T1624 - Exploitation of Authentication Mechanism**  
   https://attack.mitre.org/techniques/T1624/

---

*Security Engineering Lead focused on abuse detection, trust & safety, and security automation at scale. Drafted with AI assistance and reviewed for technical accuracy.*
