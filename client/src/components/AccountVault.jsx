import React, { useState, useEffect } from "react";
import { Plus, User, Trash2, Eye, EyeOff } from "lucide-react";
import store from "../store/db";

function AccountVault() {
  const [accounts, setAccounts] = useState([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [visiblePasswords, setVisiblePasswords] = useState({});
  const [newAccount, setNewAccount] = useState({
    platform: "",
    platformUrl: "",
    username: "",
    password: "",
    email: "",
    phone: "",
    notes: "",
    status: "active",
  });

  useEffect(() => {
    loadAccounts();
  }, []);

  const loadAccounts = async () => {
    const storedAccounts = (await store.get("accounts")) || [];
    setAccounts(storedAccounts);
  };

  const addAccount = async () => {
    const account = {
      id: `acc_${Date.now()}`,
      ...newAccount,
      banned: false,
      createdAt: new Date().toISOString(),
      lastUsed: null,
    };

    const updatedAccounts = [...accounts, account];
    await store.set("accounts", updatedAccounts);
    setAccounts(updatedAccounts);

    setShowAddModal(false);
    setNewAccount({
      platform: "",
      platformUrl: "",
      username: "",
      password: "",
      email: "",
      phone: "",
      notes: "",
      status: "active",
    });
  };

  const deleteAccount = async (accountId) => {
    if (!window.confirm("Are you sure you want to delete this account?"))
      return;

    const updatedAccounts = accounts.filter((a) => a.id !== accountId);
    await store.set("accounts", updatedAccounts);
    setAccounts(updatedAccounts);
  };

  const toggleBanned = async (accountId) => {
    const updatedAccounts = accounts.map((a) => {
      if (a.id === accountId) {
        return {
          ...a,
          banned: !a.banned,
          status: a.banned ? "active" : "banned",
        };
      }
      return a;
    });

    await store.set("accounts", updatedAccounts);
    setAccounts(updatedAccounts);
  };

  const togglePasswordVisibility = (accountId) => {
    setVisiblePasswords((prev) => ({
      ...prev,
      [accountId]: !prev[accountId],
    }));
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-white">Account Vault</h2>
        <button
          onClick={() => setShowAddModal(true)}
          className="btn btn-primary flex items-center"
        >
          <Plus className="w-4 h-4 mr-2" />
          Add Account
        </button>
      </div>

      <div className="grid gap-4">
        {accounts.map((account) => (
          <div key={account.id} className="card">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-4">
                <div
                  className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                    account.banned ? "bg-error-500/20" : "bg-primary-500/20"
                  }`}
                >
                  <User
                    className={`w-6 h-6 ${
                      account.banned ? "text-error-500" : "text-primary-500"
                    }`}
                  />
                </div>

                <div>
                  <h3 className="text-lg font-semibold text-white">
                    {account.username}
                  </h3>
                  <p className="text-sm text-dark-400">{account.platform}</p>
                  {account.platformUrl && (
                    <a
                      href={account.platformUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-primary-400 hover:underline"
                    >
                      {account.platformUrl}
                    </a>
                  )}
                </div>
              </div>

              <div className="flex items-center space-x-3">
                <button
                  onClick={() => toggleBanned(account.id)}
                  className={`btn ${account.banned ? "btn-success" : "btn-error"}`}
                >
                  {account.banned ? "Unban" : "Mark Banned"}
                </button>
                <button
                  onClick={() => deleteAccount(account.id)}
                  className="btn btn-error"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-dark-400">Email</p>
                <p className="text-white">{account.email || "N/A"}</p>
              </div>
              <div>
                <p className="text-dark-400">Phone</p>
                <p className="text-white">{account.phone || "N/A"}</p>
              </div>
              <div className="col-span-2">
                <p className="text-dark-400">Password</p>
                <div className="flex items-center space-x-2">
                  <p className="text-white font-mono">
                    {visiblePasswords[account.id]
                      ? account.password
                      : "••••••••"}
                  </p>
                  <button
                    onClick={() => togglePasswordVisibility(account.id)}
                    className="text-dark-400 hover:text-white"
                  >
                    {visiblePasswords[account.id] ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>
              {account.notes && (
                <div className="col-span-2">
                  <p className="text-dark-400">Notes</p>
                  <p className="text-white">{account.notes}</p>
                </div>
              )}
            </div>

            {account.banned && (
              <div className="mt-4 p-3 bg-error-500/10 border border-error-500/30 rounded-lg">
                <p className="text-sm text-error-500">
                  ⚠️ This account is marked as banned
                </p>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Add Account Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 overflow-y-auto">
          <div className="bg-dark-800 rounded-lg p-6 w-full max-w-md m-4">
            <h3 className="text-xl font-bold text-white mb-4">Add Account</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  Platform
                </label>
                <input
                  type="text"
                  className="input w-full"
                  placeholder="Instagram"
                  value={newAccount.platform}
                  onChange={(e) =>
                    setNewAccount({ ...newAccount, platform: e.target.value })
                  }
                />
              </div>

              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  Platform URL
                </label>
                <input
                  type="url"
                  className="input w-full"
                  placeholder="https://instagram.com"
                  value={newAccount.platformUrl}
                  onChange={(e) =>
                    setNewAccount({
                      ...newAccount,
                      platformUrl: e.target.value,
                    })
                  }
                />
              </div>

              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  Username
                </label>
                <input
                  type="text"
                  className="input w-full"
                  placeholder="myusername"
                  value={newAccount.username}
                  onChange={(e) =>
                    setNewAccount({ ...newAccount, username: e.target.value })
                  }
                />
              </div>

              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  Password
                </label>
                <input
                  type="password"
                  className="input w-full"
                  placeholder="••••••••"
                  value={newAccount.password}
                  onChange={(e) =>
                    setNewAccount({ ...newAccount, password: e.target.value })
                  }
                />
              </div>

              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  Email (optional)
                </label>
                <input
                  type="email"
                  className="input w-full"
                  placeholder="email@example.com"
                  value={newAccount.email}
                  onChange={(e) =>
                    setNewAccount({ ...newAccount, email: e.target.value })
                  }
                />
              </div>

              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  Phone (optional)
                </label>
                <input
                  type="tel"
                  className="input w-full"
                  placeholder="+1234567890"
                  value={newAccount.phone}
                  onChange={(e) =>
                    setNewAccount({ ...newAccount, phone: e.target.value })
                  }
                />
              </div>

              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  Notes (optional)
                </label>
                <textarea
                  className="input w-full"
                  rows="3"
                  placeholder="Additional notes..."
                  value={newAccount.notes}
                  onChange={(e) =>
                    setNewAccount({ ...newAccount, notes: e.target.value })
                  }
                />
              </div>
            </div>

            <div className="flex space-x-3 mt-6">
              <button
                onClick={() => setShowAddModal(false)}
                className="btn btn-secondary flex-1"
              >
                Cancel
              </button>
              <button
                onClick={addAccount}
                className="btn btn-primary flex-1"
                disabled={
                  !newAccount.platform ||
                  !newAccount.username ||
                  !newAccount.password
                }
              >
                Add Account
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AccountVault;
