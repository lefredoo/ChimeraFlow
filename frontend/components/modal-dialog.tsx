"use client";

import { useEffect, useId, useRef } from "react";

import { useI18n } from "./locale-provider";

interface ModalDialogProps {
  title: string;
  onClose: () => void;
  /** `drawer` slides in from the right edge; `confirm` is a centered box. */
  variant: "drawer" | "confirm";
  children: React.ReactNode;
}

/**
 * Modal built on the native `<dialog>` element: focus is trapped inside, Escape
 * closes it and the page behind is inert. Mount it to open, unmount to close;
 * the focus goes back to the element that opened it.
 */
export function ModalDialog({ title, onClose, variant, children }: Readonly<ModalDialogProps>) {
  const { t } = useI18n();
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (dialog === null) {
      return;
    }
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog.setAttribute("open", "");
    }
    return () => opener?.focus();
  }, []);

  return (
    <dialog
      ref={ref}
      className="modal"
      data-variant={variant}
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(event) => {
        // A click on the backdrop lands on the dialog element itself
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="modal-body glass-panel">
        <div className="modal-header">
          <h2 id={titleId} className="panel-subtitle">
            {title}
          </h2>
          <button type="button" className="button button-secondary" onClick={onClose}>
            {t("common.close")}
          </button>
        </div>
        {children}
      </div>
    </dialog>
  );
}
