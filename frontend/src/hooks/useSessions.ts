import { useSession } from '../contexts/SessionContext';

export const useSessions = () => {
  const session = useSession();
  return session;
};

