// @refresh reset
/// <reference types="react" />
/** @jsxRuntime classic */
// @ts-ignore: suppress missing React type declarations in some environments
import React, { createContext, useContext, useEffect, useState } from 'react';

type Theme = 'light'| 'dark';

interface ThemeContextType {
    theme: Theme;
    toggleTheme : () => void;
    setTheme: (theme: Theme) => void;
    isDark: boolean;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider : React.FC<{ children: React.ReactNode }>= ({ children }: { children: React.ReactNode }) => {
   const [theme, setTheme]= useState<Theme>(() => {
    const saved = localStorage.getItem('theme') as Theme;
    if(saved) return saved;
    if(window.matchMedia('(prefers-color-scheme: dark)').matches){
        return 'dark';
    }
    return 'light';
   });

   const isDark = theme == 'dark';

   useEffect(() => {
    document.documentElement.setAttribute('data-theme',theme);
    localStorage.setItem('theme',theme);

    if(isDark){
        document.documentElement.classList.add('dark');
    }else{
        document.documentElement.classList.remove('dark');
    }
    }, [theme,isDark]);
   
    const toggleTheme = () => {
        setTheme((prev: Theme) => prev === 'light' ? 'dark' : 'light');
    };

    return (
        <ThemeContext.Provider value={{ theme,toggleTheme,setTheme,isDark}}>
            {children}
        </ThemeContext.Provider>
    );
};

export const useTheme =() => {
    const context = useContext(ThemeContext);
    if(!context){
        throw new Error('useTheme must be used within a ThemeProvider');
    }
    return context;
};