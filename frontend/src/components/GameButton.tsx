
type GameButtonProps = {
  label: string;
  onClick?: () => void;
};

function GameButton({ label, onClick }: GameButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="bg-yellow-300 text-black px-8 py-4 border-[3px] border-black font-bold shadow-[5px_5px_0_#111]"
    >
      {label}
    </button>
  );
}

export default GameButton;
