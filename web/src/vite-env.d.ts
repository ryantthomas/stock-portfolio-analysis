/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Override the API origin when the frontend is served separately. */
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
