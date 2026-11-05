import type { ReactNode } from "react";
import {
  CircleAlert,
  CircleCheck,
  CircleDashed,
  CircleSlash,
  Clock,
  List,
  ListFilter,
  RefreshCw,
  WifiOff,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useDashboardStore } from "../../application/store";
import type { UnavailableKind } from "../../domain/types";
import { ProcessTable } from "./ProcessTable";

const UNAVAILABLE_LABEL: Record<UnavailableKind, string> = {
  unsupported: "Not supported on this host",
  permission: "Needs permission",
  transient: "Temporarily unavailable",
  disabled: "Disabled",
};

function StatusLine({
  icon: Icon,
  tone,
  children,
}: {
  icon: LucideIcon;
  tone: string;
  children: ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 text-xs font-medium ${tone}`}
    >
      <Icon aria-hidden="true" className="h-4 w-4" />
      {children}
    </span>
  );
}

function Message({
  icon: Icon,
  title,
  tone = "text-muted",
  children,
}: {
  icon: LucideIcon;
  title: string;
  tone?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-start gap-2 text-sm">
      <Icon
        aria-hidden="true"
        className={`h-4 w-4 shrink-0 ${tone}`}
      />
      <div>
        <p className="font-medium text-text">{title}</p>
        <p className="mt-1 text-muted">{children}</p>
      </div>
    </div>
  );
}

function LoadingBody() {
  return (
    <div role="status">
      <span className="sr-only">Loading process data</span>
      <div aria-hidden="true" className="space-y-2">
        {[0, 1, 2, 3, 4, 5].map((row) => (
          <div key={row} className="h-4 rounded-sm bg-surface-alt" />
        ))}
      </div>
    </div>
  );
}

/** Running processes panel: latest list only, with all seven data states. */
export function ProcessPanel() {
  const metricState = useDashboardStore((s) => s.metricStates.processes);
  const connection = useDashboardStore((s) => s.connectionState);
  const hasSnapshot = useDashboardStore((s) => s.latestSnapshot !== null);
  const groupPresent = useDashboardStore(
    (s) =>
      s.latestSnapshot !== null &&
      Object.prototype.hasOwnProperty.call(
        s.latestSnapshot.groups,
        "processes",
      ),
  );

  let status: ReactNode;
  let body: ReactNode;

  if (metricState.status === "error") {
    status = (
      <StatusLine icon={CircleAlert} tone="text-critical">
        Error
      </StatusLine>
    );
    body = (
      <Message icon={CircleAlert} title="Error" tone="text-critical">
        {metricState.message ?? metricState.error}
      </Message>
    );
  } else if (!hasSnapshot) {
    status = <span className="text-xs font-medium text-muted">Loading</span>;
    body = <LoadingBody />;
  } else if (!groupPresent) {
    status = (
      <StatusLine icon={CircleSlash} tone="text-muted">
        Not provided
      </StatusLine>
    );
    body = (
      <Message icon={CircleSlash} title="Not provided">
        Process data is not provided by the server in this snapshot. No
        placeholder rows are shown.
      </Message>
    );
  } else if (metricState.status === "loading") {
    status = <span className="text-xs font-medium text-muted">Loading</span>;
    body = <LoadingBody />;
  } else if (metricState.status === "unavailable") {
    status = (
      <StatusLine icon={CircleSlash} tone="text-muted">
        Unavailable
      </StatusLine>
    );
    body = (
      <Message
        icon={CircleSlash}
        title={UNAVAILABLE_LABEL[metricState.kind]}
      >
        {metricState.reason}
      </Message>
    );
  } else if (metricState.status === "disconnected") {
    status = (
      <StatusLine icon={WifiOff} tone="text-critical">
        Disconnected
      </StatusLine>
    );
    body = (
      <Message icon={WifiOff} title="Disconnected">
        No process list has been received. The table will appear when the
        connection recovers.
      </Message>
    );
  } else {
    const list = metricState.value;
    const partial = metricState.status === "partial";
    const retained = connection !== "open";
    const stale = connection === "stale" || metricState.status === "stale";
    const disconnected =
      connection === "disconnected" || connection === "fatal";
    const reconnecting = connection === "connecting";

    if (disconnected) {
      status = (
        <StatusLine icon={WifiOff} tone="text-critical">
          Disconnected · showing last received list
        </StatusLine>
      );
    } else if (stale) {
      status = (
        <StatusLine icon={Clock} tone="text-warn">
          Stale · retained reading
        </StatusLine>
      );
    } else if (reconnecting) {
      status = (
        <StatusLine icon={RefreshCw} tone="text-warn">
          Reconnecting · showing last received list
        </StatusLine>
      );
    } else if (partial) {
      status = (
        <StatusLine icon={CircleDashed} tone="text-info">
          Partial data
        </StatusLine>
      );
    } else {
      status = (
        <StatusLine icon={CircleCheck} tone="text-ok">
          Live
        </StatusLine>
      );
    }

    body = (
      <>
        <p className="mb-2 inline-flex items-center gap-1.5 text-xs text-muted">
          <ListFilter
            aria-hidden="true"
            className="h-4 w-4 shrink-0 text-primary"
          />
          <span>
            {list.total > list.items.length
              ? `Showing top ${list.items.length} of ${list.total} processes`
              : `${list.total} ${list.total === 1 ? "process" : "processes"}`}
          </span>
        </p>
        {(list.skipped > 0 || partial) && (
          <div className="mb-2 space-y-1 text-xs text-muted">
            {partial && list.skipped === 0 && (
              <p>Some CPU values are not measured yet.</p>
            )}
            {list.skipped > 0 && (
              <p>
                {list.skipped}{" "}
                {list.skipped === 1 ? "process" : "processes"} could not be read.
              </p>
            )}
          </div>
        )}
        {list.items.length === 0 ? (
          <p className="py-2 text-sm text-muted">
            No processes reported in the latest snapshot.
          </p>
        ) : (
          <div className={retained ? "opacity-60" : undefined}>
            <ProcessTable items={list.items} />
          </div>
        )}
      </>
    );
  }

  return (
    <section
      aria-label="Running processes"
      className="flex h-full min-w-0 flex-col rounded-card border border-border-subtle bg-surface p-3"
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-medium text-muted">
          <List aria-hidden="true" className="h-4 w-4 text-primary" />
          Running processes
        </h2>
        {status}
      </header>
      <div className="mt-3 min-w-0">{body}</div>
    </section>
  );
}
