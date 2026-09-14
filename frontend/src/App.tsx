import { useState } from "react";
import "./index.css";
import { Dashboard } from "./pages/Dashboard";
import { PurchaseOrders } from "./pages/PurchaseOrders";

type Tab = "dashboard" | "purchase-orders";

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");

  return (
    <div>
      <h1>AI Purchasing Agent</h1>
      <nav>
        <button onClick={() => setTab("dashboard")}>Dashboard</button>
        <button onClick={() => setTab("purchase-orders")}>Purchase Orders</button>
      </nav>
      {tab === "dashboard" ? <Dashboard /> : <PurchaseOrders />}
    </div>
  );
}
