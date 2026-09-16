import { useState } from "react";
import "./index.css";
import { Dashboard } from "./pages/Dashboard";
import { PurchaseOrders } from "./pages/PurchaseOrders";

type Tab = "dashboard" | "purchase-orders";

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");

  return (
    <div>
      <header className="app-header">
        <div className="brand">
          <h1>Purchasing Desk</h1>
        </div>
        <p className="tagline">
          Reviews purchase recommendations and supplier shortfalls, checks them against
          budget, storage and supplier limits, and asks you to approve or reject before
          anything is ordered.
        </p>
        <nav className="app-nav">
          <button className={tab === "dashboard" ? "active" : ""} onClick={() => setTab("dashboard")}>
            Run a review
          </button>
          <button className={tab === "purchase-orders" ? "active" : ""} onClick={() => setTab("purchase-orders")}>
            Purchase orders
          </button>
        </nav>
      </header>
      <main>{tab === "dashboard" ? <Dashboard /> : <PurchaseOrders />}</main>
    </div>
  );
}
