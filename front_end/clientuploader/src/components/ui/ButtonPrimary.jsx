// src/components/ui/ButtonPrimary.jsx
export function ButtonPrimary({ children, ...props }) {
  return (
    <button
      className="w-full py-2.5 bg-[#2eb39a] hover:bg-[#26a488] text-white font-semibold rounded-lg transition"
      {...props}
    >
      {children}
    </button>
  );
}
