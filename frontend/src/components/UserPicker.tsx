import { useUsers } from "@/api/users";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Select } from "@/components/ui/Select";
import { useAuth } from "@/lib/auth-context";

const PICKER_PAGE_SIZE = 100;

interface UserPickerProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
}

function UserSelect({ id, label, value, onChange, error }: UserPickerProps) {
  const { data } = useUsers(1, PICKER_PAGE_SIZE);
  return (
    <div>
      <Label htmlFor={id}>{label}</Label>
      <Select id={id} value={value} onChange={(event) => onChange(event.target.value)} error={error}>
        <option value="">Choose…</option>
        {data?.items
          .filter((user) => user.is_active)
          .map((user) => (
            <option key={user.id} value={user.id}>
              {user.full_name}
            </option>
          ))}
      </Select>
    </div>
  );
}

/**
 * Listing people needs the user:manage permission, which most people who set up delegations do not have, so
 * everyone else enters the colleague's user number.
 */
export function UserPicker(props: UserPickerProps) {
  const { hasPermission } = useAuth();
  if (hasPermission("user:manage")) return <UserSelect {...props} />;
  return (
    <div>
      <Label htmlFor={props.id}>{`${props.label} (user number)`}</Label>
      <Input
        id={props.id}
        inputMode="numeric"
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
        error={props.error}
      />
    </div>
  );
}
