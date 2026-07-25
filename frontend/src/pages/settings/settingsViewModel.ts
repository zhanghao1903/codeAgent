import type {
  SettingsConfigSummary,
  SettingsProvider,
  SettingsWebSearchProvider,
} from "../../shared/api/platoApi";
import type { ApiError } from "../../shared/api/types";
import { settingsProviderLabel } from "./settingsCopy";

export type SettingsFormState = {
  apiKey: string;
  baseUrl: string;
  model: string;
  provider: SettingsProvider;
  selectedProfile: string;
  webSearchApiKey: string;
  webFetchEnabled: boolean;
  webFetchMaxCharsPerUrl: number;
  webFetchMaxTotalChars: number;
  webFetchMaxUrls: number;
  webSearchEnabled: boolean;
  webSearchMaxResults: number;
  webSearchProvider: SettingsWebSearchProvider;
};

export type LoggingProfileOption = {
  id: string;
  label: string;
};

export type SettingsFieldError = {
  message: string;
  path: string;
};

const fallbackProviders: SettingsProvider[] = [
  "deepseek",
  "litellm",
  "openrouter",
  "openai",
  "claude",
];

export function formStateFromConfig(
  config: SettingsConfigSummary,
): SettingsFormState {
  return {
    apiKey: "",
    baseUrl:
      config.llm.baseUrl ??
      defaultBaseUrlForProvider(
        normalizeSettingsProvider(config.llm.provider),
        config,
      ),
    model: config.llm.model,
    provider: normalizeSettingsProvider(config.llm.provider),
    selectedProfile: config.logging.selectedProfile ?? "",
    webSearchApiKey: "",
    webFetchEnabled: config.webSearch.fetchEnabled,
    webFetchMaxCharsPerUrl: normalizeWebFetchMaxCharsPerUrl(
      config.webSearch.fetchMaxCharsPerUrl,
    ),
    webFetchMaxTotalChars: normalizeWebFetchMaxTotalChars(
      config.webSearch.fetchMaxTotalChars,
    ),
    webFetchMaxUrls: normalizeWebFetchMaxUrls(config.webSearch.fetchMaxUrls),
    webSearchEnabled: config.webSearch.enabled,
    webSearchMaxResults: normalizeWebSearchMaxResults(config.webSearch.maxResults),
    webSearchProvider: normalizeWebSearchProvider(config.webSearch.provider),
  };
}

export function normalizeSettingsProvider(value: string): SettingsProvider {
  return isSettingsProvider(value) ? value : "deepseek";
}

export function providerOptions(config: SettingsConfigSummary | null) {
  const options = config?.llm.providerOptions.length
    ? config.llm.providerOptions
    : fallbackProviders.map((provider) => ({
        baseUrlEnvVar:
          provider === "openai"
            ? "OPENAI_BASE_URL"
            : provider === "claude"
              ? "ANTHROPIC_BASE_URL"
              : null,
        defaultBaseUrl:
          provider === "openai"
            ? "https://api.openai.com/v1"
            : provider === "claude"
              ? "https://api.anthropic.com"
              : null,
        id: provider,
        label: settingsProviderLabel(provider),
        preferredApiKeyEnvVar: preferredApiKeyEnvVar(provider),
        requiredApiKeyEnvVars: requiredApiKeyEnvVars(provider),
      }));

  return options.map((option) => ({
    ...option,
    label: option.label || settingsProviderLabel(option.id),
  }));
}

export function webSearchProviderOptions(config: SettingsConfigSummary | null) {
  const options = config?.webSearch.providerOptions.length
    ? config.webSearch.providerOptions
    : [
        {
          id: "tavily" as const,
          label: "Tavily",
          preferredApiKeyEnvVar: "TAVILY_API_KEY",
          requiredApiKeyEnvVars: ["TAVILY_API_KEY"],
        },
      ];
  return options.map((option) => ({
    ...option,
    label: option.label || webSearchProviderLabel(option.id),
  }));
}

export function loggingProfileOptions(
  config: SettingsConfigSummary,
): LoggingProfileOption[] {
  const options = config.logging.profiles.map((profile) => ({
    id: profile.id,
    label: profile.id,
  }));
  const selectedProfile = config.logging.selectedProfile;
  const defaultProfile = config.logging.defaultProfile;

  for (const profileId of [selectedProfile, defaultProfile]) {
    if (
      typeof profileId === "string" &&
      profileId.length > 0 &&
      !options.some((option) => option.id === profileId)
    ) {
      options.push({
        id: profileId,
        label: profileId,
      });
    }
  }

  return options;
}

export function apiKeyHint(
  provider: SettingsProvider,
  config: SettingsConfigSummary | null,
): string {
  const matched = providerOptions(config).find((option) => option.id === provider);
  const envVars =
    matched?.requiredApiKeyEnvVars.length !== 0
      ? matched?.requiredApiKeyEnvVars
      : requiredApiKeyEnvVars(provider);
  return (envVars ?? requiredApiKeyEnvVars(provider)).join(" or ");
}

export function defaultBaseUrlForProvider(
  provider: SettingsProvider,
  config: SettingsConfigSummary | null,
): string {
  const matched = providerOptions(config).find((option) => option.id === provider);
  if (typeof matched?.defaultBaseUrl === "string") {
    return matched.defaultBaseUrl;
  }
  if (provider === "openai") {
    return "https://api.openai.com/v1";
  }
  if (provider === "claude") {
    return "https://api.anthropic.com";
  }
  return "";
}

export function providerUsesBaseUrl(
  provider: SettingsProvider,
  config: SettingsConfigSummary | null,
): boolean {
  const matched = providerOptions(config).find((option) => option.id === provider);
  return typeof matched?.baseUrlEnvVar === "string" && matched.baseUrlEnvVar.length > 0;
}

export function webSearchApiKeyHint(
  provider: SettingsWebSearchProvider,
  config: SettingsConfigSummary | null,
): string {
  const matched = webSearchProviderOptions(config).find(
    (option) => option.id === provider,
  );
  return (matched?.requiredApiKeyEnvVars ?? ["TAVILY_API_KEY"]).join(" or ");
}

export function normalizeWebSearchMaxResults(value: number): number {
  if (!Number.isFinite(value)) {
    return 5;
  }
  return Math.min(10, Math.max(1, Math.trunc(value)));
}

export function normalizeWebFetchMaxUrls(value: number): number {
  if (!Number.isFinite(value)) {
    return 3;
  }
  return Math.min(5, Math.max(1, Math.trunc(value)));
}

export function normalizeWebFetchMaxCharsPerUrl(value: number): number {
  if (!Number.isFinite(value)) {
    return 12000;
  }
  return Math.min(20000, Math.max(1000, Math.trunc(value)));
}

export function normalizeWebFetchMaxTotalChars(value: number): number {
  if (!Number.isFinite(value)) {
    return 24000;
  }
  return Math.min(40000, Math.max(1000, Math.trunc(value)));
}

export function fieldErrorsFromApiError(
  error: ApiError | null | undefined,
): SettingsFieldError[] {
  const raw = error?.details.fieldErrors;
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.flatMap((item) => {
    if (!isFieldErrorItem(item)) {
      return [];
    }
    return [
      {
        message: item.message,
        path: item.path,
      },
    ];
  });
}

export function fieldErrorFor(
  errors: SettingsFieldError[],
  path: string,
): string | null {
  return errors.find((error) => error.path === path)?.message ?? null;
}

function isSettingsProvider(value: string): value is SettingsProvider {
  return fallbackProviders.includes(value as SettingsProvider);
}

function normalizeWebSearchProvider(value: string): SettingsWebSearchProvider {
  return value === "tavily" ? "tavily" : "tavily";
}

function webSearchProviderLabel(provider: SettingsWebSearchProvider): string {
  if (provider === "tavily") {
    return "Tavily";
  }
  return provider;
}

function preferredApiKeyEnvVar(provider: SettingsProvider): string {
  return requiredApiKeyEnvVars(provider)[0];
}

function requiredApiKeyEnvVars(provider: SettingsProvider): string[] {
  if (provider === "deepseek") {
    return ["DEEPSEEK_API_KEY", "LLM_API_KEY"];
  }
  if (provider === "openrouter") {
    return ["OPENROUTER_API_KEY", "LLM_API_KEY"];
  }
  if (provider === "openai") {
    return ["OPENAI_API_KEY", "LLM_API_KEY"];
  }
  if (provider === "claude") {
    return ["ANTHROPIC_API_KEY", "LLM_API_KEY"];
  }
  return ["LLM_API_KEY"];
}

function isFieldErrorItem(
  item: unknown,
): item is { message: string; path: string } {
  return (
    typeof item === "object" &&
    item !== null &&
    typeof (item as { message?: unknown }).message === "string" &&
    typeof (item as { path?: unknown }).path === "string"
  );
}
