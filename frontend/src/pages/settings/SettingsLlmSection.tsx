import type {
  SettingsConfigSummary,
  SettingsReadinessReport,
} from "../../shared/api/platoApi";
import { useUiText } from "../../shared/ui-text";
import { settingsProviderLabel } from "./settingsCopy";
import {
  apiKeyHint,
  defaultBaseUrlForProvider,
  fieldErrorFor,
  providerOptions,
  providerUsesBaseUrl,
  type SettingsFieldError,
  type SettingsFormState,
} from "./settingsViewModel";
import styles from "./SettingsRoute.module.css";

type SettingsLlmSectionProps = {
  config: SettingsConfigSummary;
  disabled: boolean;
  fieldErrors: SettingsFieldError[];
  form: SettingsFormState;
  onChange: (form: SettingsFormState) => void;
};

export function SettingsLlmSection({
  config,
  disabled,
  fieldErrors,
  form,
  onChange,
}: SettingsLlmSectionProps) {
  const uiText = useUiText();
  const usesBaseUrl = providerUsesBaseUrl(form.provider, config);
  const activeProviderKeyConfigured =
    form.provider === config.llm.provider && config.llm.apiKeyConfigured;

  return (
    <div className={styles.formGrid}>
      <label className={styles.field}>
        <span>{uiText.settings.fields.provider}</span>
        <select
          aria-label={uiText.settings.fields.provider}
          disabled={disabled}
          name="provider"
          onChange={(event) => {
            const provider = event.target.value as SettingsFormState["provider"];
            onChange({
              ...form,
              apiKey: "",
              baseUrl: providerUsesBaseUrl(provider, config)
                ? defaultBaseUrlForProvider(provider, config)
                : "",
              model: "",
              provider,
            });
          }}
          value={form.provider}
        >
          {providerOptions(config).map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      {usesBaseUrl ? (
        <label className={styles.field}>
          <span>{uiText.settings.fields.baseUrl}</span>
          <input
            aria-label={uiText.settings.fields.baseUrl}
            disabled={disabled}
            name="baseUrl"
            onChange={(event) =>
              onChange({ ...form, baseUrl: event.target.value })
            }
            required
            type="url"
            value={form.baseUrl}
          />
          <LlmFieldError errors={fieldErrors} path="llm.baseUrl" />
        </label>
      ) : null}
      <label className={styles.field}>
        <span>{uiText.settings.fields.model}</span>
        <input
          aria-label={uiText.settings.fields.model}
          disabled={disabled}
          name="model"
          onChange={(event) => onChange({ ...form, model: event.target.value })}
          required
          type="text"
          value={form.model}
        />
        <LlmFieldError errors={fieldErrors} path="llm.model" />
      </label>
      <label className={styles.field}>
        <span>{uiText.settings.fields.apiKey}</span>
        <input
          aria-label={uiText.settings.fields.apiKey}
          autoComplete="off"
          disabled={disabled}
          name="apiKey"
          onChange={(event) => onChange({ ...form, apiKey: event.target.value })}
          type="password"
          value={form.apiKey}
        />
        <small>
          {activeProviderKeyConfigured
            ? uiText.settings.messages.apiKeyConfigured({
                source: config.llm.apiKeySource,
              })
            : uiText.settings.messages.apiKeyRequired({
                hint: apiKeyHint(form.provider, config),
              })}
        </small>
        <LlmFieldError errors={fieldErrors} path="llm.apiKey" />
      </label>
    </div>
  );
}

export function SettingsLlmSummary({
  config,
  readiness,
}: {
  config: SettingsConfigSummary;
  readiness: SettingsReadinessReport | null;
}) {
  const uiText = useUiText();

  return (
    <dl className={styles.summaryGrid}>
      <div>
        <dt>{uiText.settings.fields.provider}</dt>
        <dd>{settingsProviderLabel(config.llm.provider)}</dd>
      </div>
      <div>
        <dt>{uiText.settings.fields.model}</dt>
        <dd>{config.llm.model}</dd>
      </div>
      {config.llm.baseUrl ? (
        <div>
          <dt>{uiText.settings.fields.baseUrl}</dt>
          <dd>{config.llm.baseUrl}</dd>
        </div>
      ) : null}
      <div>
        <dt>{uiText.settings.fields.apiKey}</dt>
        <dd>
          {config.llm.apiKeyConfigured
            ? uiText.settings.labels.configured
            : uiText.settings.labels.missing}
        </dd>
      </div>
      <div>
        <dt>{uiText.settings.fields.readiness}</dt>
        <dd>{readiness?.status ?? uiText.settings.labels.notChecked}</dd>
      </div>
    </dl>
  );
}

function LlmFieldError({
  errors,
  path,
}: {
  errors: SettingsFieldError[];
  path: string;
}) {
  const message = fieldErrorFor(errors, path);
  if (message === null) {
    return null;
  }
  return (
    <small className={styles.fieldError} role="alert">
      {message}
    </small>
  );
}
