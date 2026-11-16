import type { Severity, SourceName } from "../lib/api-types";

/**
 * Line icons, one shape per meaning. They are decorative (`aria-hidden`): the
 * text next to each icon carries the meaning, so color is never the only cue.
 */
function Svg({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <svg
      className="icon"
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

/** Spreadsheet grid. */
function ExcelIcon() {
  return (
    <Svg>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M3 10h18M3 15h18M9 4v16" />
    </Svg>
  );
}

/** Database cylinder. */
function AccessIcon() {
  return (
    <Svg>
      <ellipse cx="12" cy="6" rx="8" ry="3" />
      <path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
    </Svg>
  );
}

/** Speech bubble. */
function WhatsAppIcon() {
  return (
    <Svg>
      <path d="M21 12a8 8 0 0 1-11.7 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z" />
      <path d="M9 10h6M9 14h4" />
    </Svg>
  );
}

/** Coin over a handset. */
function MomoIcon() {
  return (
    <Svg>
      <rect x="7" y="2.5" width="10" height="19" rx="2" />
      <circle cx="12" cy="11" r="3" />
      <path d="M11 18h2" />
    </Svg>
  );
}

export function SourceIcon({ source }: Readonly<{ source: SourceName }>) {
  switch (source) {
    case "excel":
      return <ExcelIcon />;
    case "access":
      return <AccessIcon />;
    case "whatsapp":
      return <WhatsAppIcon />;
    case "momo":
      return <MomoIcon />;
  }
}

export function SeverityIcon({ severity }: Readonly<{ severity: Severity }>) {
  switch (severity) {
    case "info":
      return (
        <Svg>
          <circle cx="12" cy="12" r="9" />
          <path d="M12 11v5M12 8h.01" />
        </Svg>
      );
    case "warning":
      return (
        <Svg>
          <path d="M12 3 2.5 20h19L12 3Z" />
          <path d="M12 10v4.5M12 17.5h.01" />
        </Svg>
      );
    case "error":
      return (
        <Svg>
          <path d="M8 3h8l5 5v8l-5 5H8l-5-5V8l5-5Z" />
          <path d="m9.5 9.5 5 5m0-5-5 5" />
        </Svg>
      );
  }
}

export function StatusIcon({ status }: Readonly<{ status: "ok" | "degraded" | "error" }>) {
  switch (status) {
    case "ok":
      return (
        <Svg>
          <path d="m5 12.5 4.5 4.5L19 7.5" />
        </Svg>
      );
    case "degraded":
      return (
        <Svg>
          <path d="M5 12h5M14 12h5" />
        </Svg>
      );
    case "error":
      return (
        <Svg>
          <path d="m6 6 12 12M18 6 6 18" />
        </Svg>
      );
  }
}

export function SunIcon() {
  return (
    <Svg>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </Svg>
  );
}

export function MoonIcon() {
  return (
    <Svg>
      <path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z" />
    </Svg>
  );
}
