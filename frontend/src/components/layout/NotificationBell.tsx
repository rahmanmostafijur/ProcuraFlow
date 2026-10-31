import { Bell } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  type AppNotification,
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
  useUnreadCount,
} from "@/api/notifications";
import { cn, formatDateTime } from "@/lib/utils";

const MAX_LISTED = 10;

export function NotificationBell() {
  const [isOpen, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const { data: unread = 0 } = useUnreadCount();
  const { data: notifications, isLoading } = useNotifications(isOpen);
  const markRead = useMarkNotificationRead();
  const markAllRead = useMarkAllNotificationsRead();

  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      buttonRef.current?.focus();
    };
    const handleOutside = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", handleKey);
    document.addEventListener("mousedown", handleOutside);
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.removeEventListener("mousedown", handleOutside);
    };
  }, [isOpen]);

  const handleSelect = (notification: AppNotification) => {
    if (!notification.is_read) markRead.mutate(notification.id);
  };

  const label = unread > 0 ? `Notifications, ${unread} unread` : "Notifications";

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-label={label}
        aria-haspopup="true"
        aria-expanded={isOpen}
        onClick={() => setOpen((open) => !open)}
        className="relative rounded-md p-2 text-slate-600 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
      >
        <Bell className="h-5 w-5" aria-hidden="true" />
        {unread > 0 && (
          <span
            aria-hidden="true"
            className="absolute -right-0.5 -top-0.5 min-w-[1.25rem] rounded-full bg-brand-600 px-1 text-center text-xs font-semibold text-white"
          >
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {isOpen && (
        <div
          role="region"
          aria-label="Recent notifications"
          className="absolute right-0 z-40 mt-2 w-80 rounded-lg border border-slate-200 bg-white shadow-lg"
        >
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2">
            <h2 className="text-sm font-semibold text-slate-900">Notifications</h2>
            <button
              type="button"
              disabled={unread === 0 || markAllRead.isPending}
              onClick={() => markAllRead.mutate()}
              className="text-xs font-medium text-brand-600 hover:underline disabled:pointer-events-none disabled:opacity-50"
            >
              Mark all read
            </button>
          </div>
          <ul className="max-h-96 divide-y divide-slate-100 overflow-y-auto">
            {isLoading && <li className="px-4 py-3 text-sm text-slate-500">Loading…</li>}
            {notifications?.length === 0 && <li className="px-4 py-3 text-sm text-slate-500">No notifications yet.</li>}
            {notifications?.slice(0, MAX_LISTED).map((notification) => (
              <li key={notification.id}>
                <button
                  type="button"
                  onClick={() => handleSelect(notification)}
                  className={cn(
                    "block w-full px-4 py-3 text-left text-sm hover:bg-slate-50",
                    notification.is_read ? "text-slate-500" : "bg-brand-50/40 font-medium text-slate-900",
                  )}
                >
                  <span className="block">{notification.message}</span>
                  <span className="mt-0.5 block text-xs font-normal text-slate-400">
                    {notification.is_read ? "" : "Unread · "}
                    {formatDateTime(notification.created_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
