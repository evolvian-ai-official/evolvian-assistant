// src/components/ui/Card.jsx
export function Card({ children }) {
  return (
    <div className="w-full max-w-md bg-[#1b2a41] border border-[#274472] rounded-2xl p-8 shadow-lg text-white">
      {children}
    </div>
  );
}
