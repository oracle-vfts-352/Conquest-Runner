
import { useId, type InputHTMLAttributes } from "react";

type TextInputProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string;
};

export default function TextInput({
  label,
  error,
  id,
  className = "",
  ...props
}: TextInputProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;

  return (
    <div className="flex w-full flex-col gap-2">
      <label
        htmlFor={inputId}
        className="text-sm font-black text-black"
      >
        {label}
      </label>

      <input
        {...props}
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={
          error ? `${inputId}-error` : props["aria-describedby"]
        }
        className={`w-full border-[3px] border-black bg-white px-4 py-3 text-black shadow-[4px_4px_0_#111] outline-none placeholder:text-gray-500 focus-visible:ring-4 focus-visible:ring-pink-400 ${className}`}
      />

      {error && (
        <p
          id={`${inputId}-error`}
          role="alert"
          className="text-sm font-bold text-red-700"
        >
          {error}
        </p>
      )}
    </div>
  );
}
