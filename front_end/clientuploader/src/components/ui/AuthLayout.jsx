// src/components/ui/AuthLayout.jsx
export default function AuthLayout({ children }) {
  return (
    <div className="min-h-screen w-screen bg-[#0f1c2e] flex items-center justify-center px-4">
      {children}
    </div>
  );
}
