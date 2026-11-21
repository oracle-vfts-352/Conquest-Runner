
export default function MapPlaceholder() {
  return (
    <section
      aria-label="Map placeholder"
      className="flex min-h-72 w-full flex-col items-center justify-center gap-3 border-[3px] border-dashed border-black bg-[#BCEFE9] p-6 text-center shadow-[6px_6px_0_#111] sm:min-h-96"
    >
      <h2 className="text-2xl font-black !text-black">
        MAP AREA
      </h2>

      <p className="text-sm text-black">
        Map component will be added here.
      </p>

      <p className="text-xs text-gray-700">
        UI Preview Only - No GPS tracking
      </p>
    </section>
  );
}
