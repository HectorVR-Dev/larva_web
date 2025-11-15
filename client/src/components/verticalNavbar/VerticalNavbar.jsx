import React, { useState, useEffect } from 'react';
import { AiOutlineHome } from "react-icons/ai";
import { LuMousePointer2 } from "react-icons/lu";
import { LuContactRound } from "react-icons/lu";
import { MdOutlineSpaceDashboard } from "react-icons/md";
import { MdOutlineSettings } from "react-icons/md";
import { LuUserRound } from "react-icons/lu";


const VerticalNavbar = ({isVisible, isChatVisible}) => {
    const [isMounted, setIsMounted] = useState(false);

    useEffect(() => {
        if (isVisible) {
            setIsMounted(true); // Activa la animación de entrada
        } else {
            setIsMounted(false); // Desactiva la animación de entrada
        }
    }, [isVisible]);

    // Clases para los efectos hover/active
    const hoverClasses = [
        'text-white/40',           // Color base
        'hover:text-white',         // Hover en desktop
        'active:text-white',        // Active en mobile
        'active:bg-blue-800',       // Active en mobile
        'transition-all',
        'transition-transform duration-300',
        'hover:scale-105',
        'active:scale-95',
        'rounded',
        'p-2',
        'block',
    ].join(' ');

    if (!isVisible) return null;

    return (
        <div
            className={` bg-blue-800 text-white/20 transition-transform duration-300 transform w-full sm:w-64 top-16 left-0 z-20`}
        >
            {/* Enlaces */}
            <div className='flex justify-center'>
                <ul className='flex flex-col items-center gap-4 text-2xl pt-10 sm:pt-20'>
                    <li>
                        <a href="#dashboard" className={`${hoverClasses} group flex items-center gap-0.5 sm:gap-1 text-white`}>
                            <MdOutlineSpaceDashboard className="text-white text-lg sm:text-2xl  group-hover:text-white" />
                            Dashboard
                        </a>
                    </li>
                    <li>
                        <a href="#users" className={`${hoverClasses} group flex items-center gap-0.5 sm:gap-1 text-white `}>
                            <LuUserRound className="text-white text-lg sm:text-2xl group-hover:text-white" />
                            Users
                        </a>
                    </li>
                    <li>
                        <a href="#settings" className={`${hoverClasses} group flex items-center gap-0.5 sm:gap-1 text-white `}>
                            <MdOutlineSettings className="text-white  text-lg sm:text-2xl group-hover:text-white" />
                            Settings
                        </a>
                    </li>
                
                    <li>
                        <a href="#inicio" className={`${hoverClasses} flex items-center gap-2`}>
                            <AiOutlineHome className="text-2xl text-white" />
                            Inicio
                        </a>
                    </li>
                    <li>
                        <a href="#nosotros" className={`${hoverClasses} flex items-center gap-2`}>
                            <LuMousePointer2 className="text-2xl text-white" />
                            Nosotros
                        </a>
                    </li>
                    
                    <li>
                        <a href="#contacto" className={`${hoverClasses} flex items-center gap-2`}>
                            <LuContactRound className="text-2xl text-white" />
                            Contacto
                        </a>
                    </li>
                </ul>
            </div>
        </div>
    );
};

export default VerticalNavbar;