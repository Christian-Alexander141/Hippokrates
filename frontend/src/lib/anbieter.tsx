// Logos der Modellanbieter (Mistral, Z.ai/GLM, Qwen, Meta …) aus lobehub/lobe-icons (MIT-Lizenz).
// Die SVGs werden beim Bauen mitgebündelt – keine Anfragen an fremde Server. Logos sind Marken
// ihrer Inhaber und dienen hier nur der Kennzeichnung, von welchem Anbieter ein Modell stammt.
import { Bot, BrainCircuit, Server } from "lucide-react";
import ai2 from "@lobehub/icons-static-svg/icons/ai2-color.svg?raw";
import aya from "@lobehub/icons-static-svg/icons/aya-color.svg?raw";
import baai from "@lobehub/icons-static-svg/icons/baai.svg?raw";
import baichuan from "@lobehub/icons-static-svg/icons/baichuan-color.svg?raw";
import chatglm from "@lobehub/icons-static-svg/icons/chatglm-color.svg?raw";
import claude from "@lobehub/icons-static-svg/icons/claude-color.svg?raw";
import codegeex from "@lobehub/icons-static-svg/icons/codegeex-color.svg?raw";
import cohere from "@lobehub/icons-static-svg/icons/cohere-color.svg?raw";
import deepseek from "@lobehub/icons-static-svg/icons/deepseek-color.svg?raw";
import dolphin from "@lobehub/icons-static-svg/icons/dolphin.svg?raw";
import doubao from "@lobehub/icons-static-svg/icons/doubao-color.svg?raw";
import gemini from "@lobehub/icons-static-svg/icons/gemini-color.svg?raw";
import gemma from "@lobehub/icons-static-svg/icons/gemma-color.svg?raw";
import huggingface from "@lobehub/icons-static-svg/icons/huggingface-color.svg?raw";
import hunyuan from "@lobehub/icons-static-svg/icons/hunyuan-color.svg?raw";
import ibm from "@lobehub/icons-static-svg/icons/ibm.svg?raw";
import internlm from "@lobehub/icons-static-svg/icons/internlm-color.svg?raw";
import jina from "@lobehub/icons-static-svg/icons/jina.svg?raw";
import kimi from "@lobehub/icons-static-svg/icons/kimi-color.svg?raw";
import lg from "@lobehub/icons-static-svg/icons/lg-color.svg?raw";
import lmstudio from "@lobehub/icons-static-svg/icons/lmstudio.svg?raw";
import meta from "@lobehub/icons-static-svg/icons/meta-color.svg?raw";
import microsoft from "@lobehub/icons-static-svg/icons/microsoft-color.svg?raw";
import minimax from "@lobehub/icons-static-svg/icons/minimax-color.svg?raw";
import mistral from "@lobehub/icons-static-svg/icons/mistral-color.svg?raw";
import nousresearch from "@lobehub/icons-static-svg/icons/nousresearch.svg?raw";
import nvidia from "@lobehub/icons-static-svg/icons/nvidia-color.svg?raw";
import ollama from "@lobehub/icons-static-svg/icons/ollama.svg?raw";
import openai from "@lobehub/icons-static-svg/icons/openai.svg?raw";
import qwen from "@lobehub/icons-static-svg/icons/qwen-color.svg?raw";
import rwkv from "@lobehub/icons-static-svg/icons/rwkv-color.svg?raw";
import snowflake from "@lobehub/icons-static-svg/icons/snowflake-color.svg?raw";
import stability from "@lobehub/icons-static-svg/icons/stability-color.svg?raw";
import stepfun from "@lobehub/icons-static-svg/icons/stepfun-color.svg?raw";
import tii from "@lobehub/icons-static-svg/icons/tii-color.svg?raw";
import upstage from "@lobehub/icons-static-svg/icons/upstage-color.svg?raw";
import vllm from "@lobehub/icons-static-svg/icons/vllm-color.svg?raw";
import wenxin from "@lobehub/icons-static-svg/icons/wenxin-color.svg?raw";
import xai from "@lobehub/icons-static-svg/icons/xai.svg?raw";
import yi from "@lobehub/icons-static-svg/icons/yi-color.svg?raw";
import zai from "@lobehub/icons-static-svg/icons/zai.svg?raw";

interface Anbieter { name: string; svg: string }

// Reihenfolge zählt: spezifische Namen vor allgemeinen („llama3.1-nemotron“ ist NVIDIA, nicht Meta).
// Jede Regel wird auf jeden Pfadteil des Namens angewandt („mistralai/Mistral-7B…“, „hf.co/Qwen/…“).
const REGELN: [RegExp, Anbieter][] = [
  [/nemotron|^nvidia/, { name: "NVIDIA", svg: nvidia }],
  [/^(mistral|mixtral|codestral|ministral|magistral|devstral|pixtral|mathstral|voxtral)/, { name: "Mistral AI", svg: mistral }],
  [/^chatglm/, { name: "Zhipu ChatGLM", svg: chatglm }],
  [/^codegeex/, { name: "Zhipu CodeGeeX", svg: codegeex }],
  [/^(glm|zai|thudm)/, { name: "Z.ai (GLM)", svg: zai }],
  [/^(qwen|qwq|codeqwen)/, { name: "Qwen (Alibaba)", svg: qwen }],
  [/^(code)?gemma|^(shield|embedding|med)gemma|^paligemma/, { name: "Google Gemma", svg: gemma }],
  [/^gemini/, { name: "Google Gemini", svg: gemini }],
  [/^deepseek/, { name: "DeepSeek", svg: deepseek }],
  [/^(granite|ibm)/, { name: "IBM Granite", svg: ibm }],
  [/^(phi\d|phi-|microsoft|wizardlm|orca)/, { name: "Microsoft", svg: microsoft }],
  [/^(gpt-|o[134]-|openai)/, { name: "OpenAI", svg: openai }],
  [/^(code)?llama|^meta|^tinyllama/, { name: "Meta Llama", svg: meta }],
  [/^aya/, { name: "Cohere Aya", svg: aya }],
  [/^(command|c4ai|cohere)/, { name: "Cohere", svg: cohere }],
  [/^(yi[-:.\d]|yi$|01-ai)/, { name: "01.AI Yi", svg: yi }],
  [/^internlm/, { name: "InternLM", svg: internlm }],
  [/^(kimi|moonshot)/, { name: "Moonshot Kimi", svg: kimi }],
  [/^minimax/, { name: "MiniMax", svg: minimax }],
  [/^(hermes|nous)/, { name: "Nous Research", svg: nousresearch }],
  [/^dolphin/, { name: "Dolphin", svg: dolphin }],
  [/^falcon|^tiiuae/, { name: "TII Falcon", svg: tii }],
  [/^(olmo|tulu|allenai)/, { name: "Ai2", svg: ai2 }],
  [/^(smollm|zephyr|starcoder)/, { name: "Hugging Face", svg: huggingface }],
  [/^exaone/, { name: "LG EXAONE", svg: lg }],
  [/^(bge|baai)/, { name: "BAAI", svg: baai }],
  [/^snowflake/, { name: "Snowflake", svg: snowflake }],
  [/^jina/, { name: "Jina AI", svg: jina }],
  [/^grok|^xai/, { name: "xAI", svg: xai }],
  [/^(stablelm|stable-code|stability)/, { name: "Stability AI", svg: stability }],
  [/^rwkv/, { name: "RWKV", svg: rwkv }],
  [/^solar|^upstage/, { name: "Upstage", svg: upstage }],
  [/^hunyuan/, { name: "Tencent Hunyuan", svg: hunyuan }],
  [/^ernie/, { name: "Baidu ERNIE", svg: wenxin }],
  [/^baichuan/, { name: "Baichuan", svg: baichuan }],
  [/^(doubao|seed-)/, { name: "ByteDance Doubao", svg: doubao }],
  [/^step/, { name: "StepFun", svg: stepfun }],
  [/^claude/, { name: "Anthropic Claude", svg: claude }],
];

// Ollama-Familien als Rückfall, wenn der Name nichts verrät (z. B. eigene Modelfiles)
const FAMILIEN: Record<string, string> = {
  qwen: "qwen", qwen2: "qwen", qwen3: "qwen", qwen35: "qwen", qwen3moe: "qwen", qwen2moe: "qwen",
  gemma: "gemma", gemma2: "gemma", gemma3: "gemma", granite: "granite", granitemoe: "granite",
  gptoss: "gpt-oss", phi3: "phi3", deepseek2: "deepseek", mistral3: "mistral", command: "command-r",
  glm4: "glm", glm4moe: "glm", olmo: "olmo", exaone: "exaone", nemotron: "nemotron",
};

export function anbieterVon(modellId: string, familie = ""): Anbieter | null {
  const name = modellId.includes("::") ? modellId.split("::").slice(1).join("::") : modellId;
  const teile = name.toLowerCase().replace(/^hf\.co\//, "").split("/");
  for (const teil of [...teile].reverse()) {
    const treffer = REGELN.find(([r]) => r.test(teil));
    if (treffer) return treffer[1];
  }
  const ersatz = FAMILIEN[familie.toLowerCase()];
  return ersatz ? anbieterVon(ersatz) : null;
}

/** Logo des Anbieters eines Modells; neutrales Symbol, wenn der Anbieter unbekannt ist. */
export function AnbieterLogo({ modell, familie, groesse = 16 }: { modell: string; familie?: string; groesse?: number }) {
  const stil = { fontSize: groesse, width: groesse, height: groesse };
  if (modell.startsWith("netz::")) {
    return <span className="anbieter-logo eigen" style={stil} title="Eigenes neuronales Netz"><BrainCircuit aria-hidden /></span>;
  }
  const a = anbieterVon(modell, familie);
  if (!a) return <span className="anbieter-logo unbekannt" style={stil} title="Anbieter unbekannt"><Bot aria-hidden /></span>;
  // Statische SVGs aus dem npm-Paket (keine Nutzereingaben) – direktes Einbetten, damit einfarbige
  // Logos über currentColor der Textfarbe folgen (hell/dunkel).
  return <span className="anbieter-logo" style={stil} title={a.name} role="img" aria-label={a.name} dangerouslySetInnerHTML={{ __html: a.svg }} />;
}

const QUELLEN: Record<string, string> = { ollama, lmstudio, vllm, textgen: huggingface };

/** Logo einer Modellquelle (Ollama, LM Studio, vLLM …). */
export function QuellenLogo({ quelle, art, groesse = 15 }: { quelle: string; art?: string; groesse?: number }) {
  const stil = { fontSize: groesse, width: groesse, height: groesse };
  if (art === "netz" || quelle === "netz") return <span className="anbieter-logo eigen" style={stil}><BrainCircuit aria-hidden /></span>;
  const svg = QUELLEN[quelle] ?? (quelle.includes("vllm") ? vllm : quelle.includes("lmstudio") ? lmstudio : undefined);
  if (!svg) return <span className="anbieter-logo unbekannt" style={stil}><Server aria-hidden /></span>;
  return <span className="anbieter-logo" style={stil} aria-hidden dangerouslySetInnerHTML={{ __html: svg }} />;
}
