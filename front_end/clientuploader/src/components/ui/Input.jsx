// src/components/ui/Input.jsx
export function Input({ type = "text", ...props }) {
  return (
    <input
      type={type}
      className="w-full px-4 py-2 border border-[#274472] rounded-lg bg-transparent text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#4a90e2]"
      {...props}
    />
  );
}
