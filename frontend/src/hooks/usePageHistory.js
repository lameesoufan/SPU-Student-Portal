import { useState, useEffect, useCallback, useRef } from 'react';

export default function usePageHistory(initialPage) {
  if (initialPage === undefined) initialPage = 'dashboard';

  const [page, setPageInternal] = useState(initialPage);
  const initialPageRef = useRef(initialPage);

  useEffect(function () {
    window.history.replaceState({ page: initialPageRef.current }, '');

    function handlePopState(e) {
      if (e.state && e.state.page !== undefined) {
        setPageInternal(e.state.page);
      } else {
        setPageInternal(initialPageRef.current);
      }
    }

    window.addEventListener('popstate', handlePopState);
    return function () {
      window.removeEventListener('popstate', handlePopState);
    };
  }, []);

  var setPage = useCallback(function (newPage) {
    setPageInternal(newPage);
    window.history.pushState({ page: newPage }, '');
  }, []);

  var goBack = useCallback(function () {
    window.history.back();
  }, []);

  return [page, setPage, goBack];
}