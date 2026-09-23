import { Plus } from "lucide-react";
import { useState } from "react";

import { extractErrorMessage } from "@/api/client";
import { useCreateUser, useUpdateUser, useUsers } from "@/api/users";
import type { User } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { Pagination } from "@/components/ui/Pagination";
import { useToast } from "@/components/ui/toast-context";
import { formatDate } from "@/lib/utils";

import { UserFormModal } from "./UserFormModal";

const PAGE_SIZE = 15;

export function UsersPage() {
  const { showToast } = useToast();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [isModalOpen, setModalOpen] = useState(false);

  const { data, isLoading } = useUsers(page, PAGE_SIZE, search || undefined);
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();

  const columns: Column<User>[] = [
    { header: "Name", accessor: (row) => <span className="font-medium text-slate-900">{row.full_name}</span> },
    { header: "Email", accessor: (row) => row.email },
    { header: "Role", accessor: (row) => <span className="capitalize">{row.role.name.replace(/_/g, " ")}</span> },
    {
      header: "Status",
      accessor: (row) => (
        <Badge status={row.is_active ? "active" : "inactive"}>{row.is_active ? "Active" : "Inactive"}</Badge>
      ),
    },
    { header: "Joined", accessor: (row) => formatDate(row.created_at) },
  ];

  const openCreate = () => {
    setEditingUser(null);
    setModalOpen(true);
  };

  const openEdit = (user: User) => {
    setEditingUser(user);
    setModalOpen(true);
  };

  const handleSubmit = async (values: {
    email: string;
    full_name: string;
    password?: string;
    role_id: number;
    is_active?: boolean;
  }) => {
    try {
      if (editingUser) {
        await updateUser.mutateAsync({
          id: editingUser.id,
          full_name: values.full_name,
          role_id: values.role_id,
          is_active: values.is_active,
          password: values.password || undefined,
        });
        showToast("User updated");
      } else {
        await createUser.mutateAsync({
          email: values.email,
          full_name: values.full_name,
          password: values.password ?? "",
          role_id: values.role_id,
        });
        showToast("User created");
      }
      setModalOpen(false);
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Users</h1>
          <p className="text-sm text-slate-500">Manage team access and roles.</p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" /> New User
        </Button>
      </div>

      <Card>
        <div className="border-b border-slate-200 p-4">
          <Input
            placeholder="Search users…"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            className="max-w-xs"
          />
        </div>
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          keyExtractor={(row) => row.id}
          isLoading={isLoading}
          emptyTitle="No users found"
          onRowClick={openEdit}
        />
        {data && (
          <Pagination
            page={data.page}
            totalPages={data.total_pages}
            total={data.total}
            pageSize={data.page_size}
            onPageChange={setPage}
          />
        )}
      </Card>

      <UserFormModal
        isOpen={isModalOpen}
        onClose={() => setModalOpen(false)}
        user={editingUser}
        onSubmit={handleSubmit}
        isSubmitting={createUser.isPending || updateUser.isPending}
      />
    </div>
  );
}
