/**
 * useNotificationAlerts — fires an OS-level browser notification when a new
 * actionable request arrives in the seller's inbox. No audio, works in noisy environments.
 *
 * Permission is requested once on mount. If denied, silently does nothing.
 * Each notification fires at most once per session.
 */
import { useEffect, useRef } from "react";
import type { NotificationDTO } from "../../api/client";

async function requestPermission(): Promise<void> {
  if (!("Notification" in window)) return;
  if (Notification.permission === "default") {
    await Notification.requestPermission();
  }
}

function pushNotification(n: NotificationDTO): void {
  if (!("Notification" in window) || Notification.permission !== "granted") return;

  const canLabel = n.verdict.can_fulfil === "yes" ? "You can fulfil this" : "Partial match";
  const body =
    `${n.qty} ${n.qty === 1 ? "unit" : "units"} needed within ${n.need_in_days} days. ` +
    `${canLabel}. ${n.verdict.reasons[0] ?? ""}`.trim();

  const notif = new Notification(`New request: ${n.item}`, {
    body,
    icon: "/favicon.svg",
    tag: `crossover-rfq-${n.id}`,
    requireInteraction: false,
  });

  notif.onclick = () => { window.focus(); notif.close(); };
}

export function useNotificationAlerts(notifications: NotificationDTO[] | null): void {
  const alertedIds = useRef<Set<string>>(new Set());

  useEffect(() => { requestPermission(); }, []);

  useEffect(() => {
    if (!notifications) return;
    for (const n of notifications) {
      if (alertedIds.current.has(n.id)) continue;
      if (n.verdict.can_fulfil === "no" || n.status !== "new") {
        alertedIds.current.add(n.id);
        continue;
      }
      alertedIds.current.add(n.id);
      pushNotification(n);
      break;
    }
  }, [notifications]);
}
