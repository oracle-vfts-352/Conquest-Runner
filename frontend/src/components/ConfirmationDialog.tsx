
import { useEffect, useRef } from "react";

type ConfirmationDialogProps = {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export default function ConfirmationDialog({
  open,
  onCancel,
  onConfirm,
}: ConfirmationDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;

    if (!dialog) return;

    if (open && !dialog.open) {
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="run-dialog-title"
      onCancel={(event) => {
        event.preventDefault();
        onCancel();
      }}
      className="w-[90vw] max-w-md border-[3px] border-black bg-white p-6 text-black shadow-[8px_8px_0_#111] backdrop:bg-black/60"
    >
      <h2
        id="run-dialog-title"
        className="text-2xl font-black !text-black"
      >
        START A RUN?
      </h2>

      <p className="mt-3 text-gray-700">
        Are you ready to start your run?
      </p>

      <p className="mt-2 text-sm text-gray-600">
        UI preview only. GPS tracking is not connected.
      </p>

      <div className="mt-6 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={onCancel}
          className="border-2 border-black bg-pink-300 px-5 py-3 font-bold text-black"
        >
          CANCEL
        </button>

        <button
          type="button"
          onClick={onConfirm}
          className="border-2 border-black bg-teal-300 px-5 py-3 font-bold text-black"
        >
          CONFIRM
        </button>
      </div>
    </dialog>
  );
}
