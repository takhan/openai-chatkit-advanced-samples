import { StartScreenPrompt } from "@openai/chatkit";

export const CHATKIT_API_URL =
  import.meta.env.VITE_CHATKIT_API_URL ?? "/chatkit";

/**
 * ChatKit still expects a domain key at runtime. Use any placeholder locally,
 * but register your production domain at
 * https://platform.openai.com/settings/organization/security/domain-allowlist
 * and deploy the real key.
 */
export const CHATKIT_API_DOMAIN_KEY =
  import.meta.env.VITE_CHATKIT_API_DOMAIN_KEY ?? "domain_pk_localhost_dev";

export const FACTS_API_URL = import.meta.env.VITE_FACTS_API_URL ?? "/facts";

export const THEME_STORAGE_KEY = "chatkit-boilerplate-theme";

export const GREETING = "Welcome to Seller Assistant";

export const STARTER_PROMPTS: StartScreenPrompt[] = [
  {
    label: "How do I handle returns?",
    prompt: "How do I handle customer returns on Amazon?",
    icon: "circle-question",
  },
  {
    label: "FBA prep requirements",
    prompt: "What are the FBA prep and shipping requirements?",
    icon: "book-open",
  },
  {
    label: "Optimize my listings",
    prompt: "How can I optimize my product listings for better search ranking?",
    icon: "search",
  },
  {
    label: "Inventory management",
    prompt: "How do I manage my FBA inventory levels?",
    icon: "sparkle",
  },
];

export const PLACEHOLDER_INPUT = "Ask me about Amazon seller policies and procedures";
