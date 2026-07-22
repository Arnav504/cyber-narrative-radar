import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  fetchOrganizations,
  organizationRef,
  type Organization,
} from "../lib/api";

export type SelectedOrganization = {
  id: string;
  slug: string;
  name: string;
  sector: string;
};

type OrganizationContextValue = {
  selected: SelectedOrganization | null;
  selectOrganization: (org: Organization | null) => void;
  ready: boolean;
};

const OrganizationContext = createContext<OrganizationContextValue | null>(null);

function toSelected(org: Organization): SelectedOrganization {
  return {
    id: org.id,
    slug: organizationRef(org),
    name: org.name,
    sector: org.sector,
  };
}

export function OrganizationProvider({ children }: { children: ReactNode }) {
  const [selected, setSelected] = useState<SelectedOrganization | null>(null);
  const [ready, setReady] = useState(false);
  const bootstrappedRef = useRef(false);

  const selectOrganization = useCallback((org: Organization | null) => {
    setSelected(org ? toSelected(org) : null);
  }, []);

  useEffect(() => {
    if (bootstrappedRef.current) {
      return;
    }
    bootstrappedRef.current = true;

    const controller = new AbortController();

    async function bootstrap() {
      try {
        const orgs = await fetchOrganizations();
        if (controller.signal.aborted) {
          return;
        }
        if (orgs.length > 0) {
          const ranked = [...orgs].sort(
            (a, b) => (b.max_score ?? b.risk_score) - (a.max_score ?? a.risk_score),
          );
          setSelected(toSelected(ranked[0]));
        }
      } catch {
        // Pages handle empty/error states if bootstrap fails.
      } finally {
        if (!controller.signal.aborted) {
          setReady(true);
        }
      }
    }

    void bootstrap();
    return () => controller.abort();
  }, []);

  const value = useMemo(
    () => ({ selected, selectOrganization, ready }),
    [selected, selectOrganization, ready],
  );

  return (
    <OrganizationContext.Provider value={value}>
      {children}
    </OrganizationContext.Provider>
  );
}

export function useSelectedOrganization(): OrganizationContextValue {
  const ctx = useContext(OrganizationContext);
  if (!ctx) {
    throw new Error("useSelectedOrganization must be used within OrganizationProvider");
  }
  return ctx;
}
