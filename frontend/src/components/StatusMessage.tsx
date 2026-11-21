
type StatusType = "loading" | "empty" | "error" | "success";

type StatusMessageProps = {
  type: StatusType;
  message: string;
};

const colors = {
  loading: "bg-[#39DCCA]",
  empty: "bg-[#F9EA49]",
  error: "bg-[#FF9BCC]",
  success: "bg-[#FFBB81]",
};

const titles = {
  loading: "LOADING",
  empty: "EMPTY",
  error: "ERROR",
  success: "SUCCESS",
};

export default function StatusMessage({
  type,
  message,
}: StatusMessageProps) {
  return (
    <section
      role={type === "error" ? "alert" : "status"}
      className={`w-full border-[3px] border-black p-4 shadow-[5px_5px_0_#111] ${colors[type]}`}
    >
      <h2 className="text-lg font-black !text-black">
        {titles[type]}
      </h2>

      <p className="mt-2 text-sm text-black">
        {message}
      </p>
    </section>
  );
}
