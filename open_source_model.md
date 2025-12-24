# Integrating Hugging Face Models with LlamaIndex

## Basic Integration for Research and Experimentation

We can integrate a model from Hugging Face with LlamaIndex using the following code:

```python
from llama_index.llms.huggingface import HuggingFaceLLM
from llama_index.core import Settings

llm = HuggingFaceLLM(
    model_name="HuggingFaceH4/zephyr-7b-beta",
    tokenizer_name="HuggingFaceH4/zephyr-7b-beta",
    device_map="auto",
    model_kwargs={
        "load_in_4bit": True,  # Quantization
    },
    generate_kwargs={
        "temperature": 0.7,
        "max_new_tokens": 256,
    },
)

Settings.llm = llm
response = llm.complete("What is machine learning?")
```

This approach is typically sufficient for research and experimentation purposes.

## Using vLLM for Production Environments

Alternatively, we might want to utilize vLLM, which provides better latency and throughput, making it suitable for production environments. vLLM includes features such as paged attention to optimize performance.

We can start a local vLLM server as follows:

```bash
vllm serve Qwen/Qwen2.5-1.5B-Instruct
```

Then connect to it using:

```python
vllm_model = HuggingFaceInferenceAPI(model="http://localhost:8080")
vllm_model.complete("What is machine learning?")
```

## Selecting the Right Model

To determine which open-source model we should utilize, we should run some experiments. The size of the model we can use is constrained by the amount of available GPU memory. For optimal performance, we might want to explore models fine-tuned for medical domains, such as:

- [ClinicalCamel-70B](https://huggingface.co/wanglab/ClinicalCamel-70B)
- [Llama3-OpenBioLLM-8B](https://huggingface.co/aaditya/Llama3-OpenBioLLM-8B)

We can use our standard evaluation benchmarks to determine which model performs best. While open-source models can generally underperform compared to high-performing closed-source models such as Gemini 3.0, using a medical domain-focused model can help mitigate this performance gap.

In terms of reproducibility, using open‑source models improves reproducibility by allowing fixed model versions, deterministic decoding settings, and offline evaluation without API drift. Model version changes and settings can be more opaque for closed sourced models. 

## Managing Context Length Constraints

Open-source models typically come with shorter context lengths than Gemini 3.0, which is an important factor to consider. To reduce context length usage, we can call the LLM for each document separately, ensuring that the context includes only a single document at a time. We would perform the extraction separately and then merge the output JSONs.

### Conflict Resolution Strategy

For a particular field, if there is no conflict, we accept the extracted value. If a conflict is detected, we can use one of two approaches: make an additional LLM call for conflict resolution, or alternatively, use the log probabilities from the previous extraction to resolve the conflict utilizing the citations and quotes. Another approach could be using predefined heuristics, such as a priority list of documents for each field.

### Confidence Score Calculation

For the confidence score calculation, if all three extractions match, we assign the highest confidence score. For weaker cases where fewer extractions agree, we reduce the score accordingly. We can develop a more deterministic formula to quantify the confidence based on the number of matching extractions and their associated log probabilities.
