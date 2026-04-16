import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

def render_biomech_tab(df_plot, df_plot_resampled):  # noqa: C901
    st.header("Biomechaniczny Stres")
    
    if 'torque_smooth' in df_plot_resampled.columns:
        fig_b = go.Figure()
        
        # 1. MOMENT OBROTOWY (Oś Lewa)
        # Kolor różowy/magenta - symbolizuje napięcie/siłę
        fig_b.add_trace(go.Scatter(
            x=df_plot_resampled['time_min'], 
            y=df_plot_resampled['torque_smooth'], 
            name='Moment (Torque)', 
            line=dict(color='#e377c2', width=1.5), 
            hovertemplate="Moment: %{y:.1f} Nm<extra></extra>"
        ))
        
        # 2. KADENCJA (Oś Prawa)
        # Kolor cyan/turkus - symbolizuje szybkość/obroty
        if 'cadence_smooth' in df_plot_resampled.columns:
            fig_b.add_trace(go.Scatter(
                x=df_plot_resampled['time_min'], 
                y=df_plot_resampled['cadence_smooth'], 
                name='Kadencja', 
                yaxis="y2", # Druga oś
                line=dict(color='#19d3f3', width=1.5), 
                hovertemplate="Kadencja: %{y:.0f} RPM<extra></extra>"
            ))
        
        # LAYOUT (Unified Hover)
        fig_b.update_layout(
            template="plotly_dark",
            title="Analiza Generowania Mocy (Siła vs Szybkość)",
            hovermode="x unified",
            
            # Oś X - Czas
            xaxis=dict(
                title="Czas [min]",
                tickformat=".0f",
                hoverformat=".0f"
            ),
            
            # Oś Lewa
            yaxis=dict(title="Moment [Nm]"),
            
            # Oś Prawa
            yaxis2=dict(
                title="Kadencja [RPM]", 
                overlaying="y", 
                side="right", 
                showgrid=False
            ),
            
            legend=dict(orientation="h", y=1.1, x=0),
            margin=dict(l=10, r=10, t=40, b=10),
            height=450
        )
        
        st.plotly_chart(fig_b, use_container_width=True)
        
        st.info("""
        **💡 Kompendium: Moment Obrotowy (Siła) vs Kadencja (Szybkość)**

        Wykres pokazuje, w jaki sposób generujesz moc.
        Pamiętaj: `Moc = Moment x Kadencja`. Tę samą moc (np. 200W) możesz uzyskać "siłowo" (50 RPM) lub "szybkościowo" (100 RPM).

        **1. Interpretacja Stylu Jazdy:**
        * **Grinding (Niska Kadencja < 70, Wysoki Moment):**
            * **Fizjologia:** Dominacja włókien szybkokurczliwych (beztlenowych). Szybkie zużycie glikogenu.
            * **Skutek:** "Betonowe nogi" na biegu.
            * **Ryzyko:** Przeciążenie stawu rzepkowo-udowego (ból kolan) i odcinka lędźwiowego.
        * **Spinning (Wysoka Kadencja > 90, Niski Moment):**
            * **Fizjologia:** Przeniesienie obciążenia na układ krążenia (serce i płuca). Lepsze ukrwienie mięśni (pompa mięśniowa).
            * **Skutek:** Świeższe nogi do biegu (T2).
            * **Wyzwanie:** Wymaga dobrej koordynacji nerwowo-mięśniowej (żeby nie podskakiwać na siodełku).

        **2. Praktyczne Przykłady (Kiedy co stosować?):**
        * **Podjazd:** Naturalna tendencja do spadku kadencji. **Błąd:** "Przepychanie" na twardym biegu. **Korekta:** Zredukuj bieg, utrzymaj 80+ RPM, nawet jeśli prędkość spadnie. Oszczędzisz mięśnie.
        * **Płaski odcinek (TT):** Utrzymuj "Sweet Spot" kadencji (zazwyczaj 85-95 RPM). To balans między zmęczeniem mięśniowym a sercowym.
        * **Finisz / Atak:** Chwilowe wejście w wysoki moment I wysoką kadencję. Kosztowne energetycznie, ale daje max prędkość.

        **3. Możliwe Komplikacje i Sygnały Ostrzegawcze:**
        * **Ból przodu kolana:** Zbyt duży moment obrotowy (za twarde przełożenia). -> Zwiększ kadencję.
        * **Ból bioder / "skakanie":** Zbyt wysoka kadencja przy słabej stabilizacji (core). -> Wzmocnij brzuch lub nieco zwolnij obroty.
        * **Drętwienie stóp:** Często wynik ciągłego nacisku przy niskiej kadencji. Wyższa kadencja poprawia krążenie (faza luzu w obrocie).
        """)
    
    st.divider()
    st.subheader("Wpływ Momentu na Oksydację (Torque vs SmO2)")
    
    if 'torque' in df_plot.columns and 'smo2' in df_plot.columns:
        # Przygotowanie danych (Binning)
        df_bins = df_plot.copy()
        # Grupujemy moment co 2 Nm
        df_bins['Torque_Bin'] = (df_bins['torque'] // 2 * 2).astype(int)
        
        # Liczymy statystyki dla każdego koszyka
        bin_stats = df_bins.groupby('Torque_Bin')['smo2'].agg(['mean', 'std', 'count']).reset_index()
        # Filtrujemy szum (musi być min. 10 próbek dla danej siły)
        bin_stats = bin_stats[bin_stats['count'] > 10]
        
        fig_ts = go.Figure()
        
        # 1. GÓRNA GRANICA (Mean + STD) - Niewidoczna linia, potrzebna do cieniowania
        fig_ts.add_trace(go.Scatter(
            x=bin_stats['Torque_Bin'], 
            y=bin_stats['mean'] + bin_stats['std'], 
            mode='lines', 
            line=dict(width=0), 
            showlegend=False, 
            name='Górny zakres (+1SD)',
            hovertemplate="Max (zakres): %{y:.1f}%<extra></extra>"
        ))
        
        # 2. DOLNA GRANICA (Mean - STD) - Wypełnienie
        fig_ts.add_trace(go.Scatter(
            x=bin_stats['Torque_Bin'], 
            y=bin_stats['mean'] - bin_stats['std'], 
            mode='lines', 
            line=dict(width=0), 
            fill='tonexty', # Wypełnia do poprzedniej ścieżki (Górnej granicy)
            fillcolor='rgba(255, 75, 75, 0.15)', # Lekka czerwień
            showlegend=False, 
            name='Dolny zakres (-1SD)',
            hovertemplate="Min (zakres): %{y:.1f}%<extra></extra>"
        ))
        
        # 3. ŚREDNIA (Główna Linia)
        fig_ts.add_trace(go.Scatter(
            x=bin_stats['Torque_Bin'], 
            y=bin_stats['mean'], 
            mode='lines+markers', 
            name='Średnie SmO2', 
            line=dict(color='#FF4B4B', width=3), 
            marker=dict(size=6, color='#FF4B4B', line=dict(width=1, color='white')),
            hovertemplate="<b>Śr. SmO2:</b> %{y:.1f}%<extra></extra>"
        ))
        
        # LAYOUT (Unified Hover)
        fig_ts.update_layout(
            template="plotly_dark",
            title="Agregacja: Jak Siła (Moment) wpływa na Tlen (SmO2)?",
            hovermode="x unified",
            xaxis=dict(title="Moment Obrotowy [Nm]"),
            yaxis=dict(title="SmO2 [%]"),
            legend=dict(orientation="h", y=1.1, x=0),
            margin=dict(l=10, r=10, t=40, b=10),
            height=450
        )
        
        st.plotly_chart(fig_ts, use_container_width=True)
        
        st.info("""
        **💡 Fizjologia Okluzji (Analiza Koszykowa):**
        
        **Mechanizm Okluzji:** Kiedy mocno napinasz mięsień (wysoki moment), ciśnienie wewnątrzmięśniowe przewyższa ciśnienie w naczyniach włosowatych. Krew przestaje płynąć, tlen nie dociera, a metabolity (kwas mlekowy) nie są usuwane. To "duszenie" mięśnia od środka.
        
        **Punkt Krytyczny:** Szukaj momentu (na osi X), gdzie czerwona linia gwałtownie opada w dół. To Twój limit siłowy. Powyżej tej wartości generujesz waty 'na kredyt' beztlenowy.
        
        **Praktyczny Wniosek (Scenario):** * Masz do wygenerowania 300W. Możesz to zrobić siłowo (70 RPM, wysoki moment) lub kadencyjnie (90 RPM, niższy moment).
        * Spójrz na wykres: Jeśli przy momencie odpowiadającym 70 RPM Twoje SmO2 spada do 30%, a przy momencie dla 90 RPM wynosi 50% -> **Wybierz wyższą kadencję!** Oszczędzasz nogi (glikogen) kosztem nieco wyższego tętna.
        """)

    # =========================================================================
    # SEKCJA: PULSE POWER (EFICIENCY)
    # =========================================================================
    st.divider()
    st.subheader("🫀 Pulse Power (Moc na Uderzenie Serca)")
    
    if 'watts_smooth' in df_plot_resampled.columns and 'heartrate_smooth' in df_plot_resampled.columns:
        import numpy as np
        from scipy import stats
        
        mask_pp = (df_plot_resampled['watts_smooth'] > 50) & (df_plot_resampled['heartrate_smooth'] > 90)
        df_pp = df_plot_resampled[mask_pp].copy()
        
        if not df_pp.empty:
            df_pp['pulse_power'] = df_pp['watts_smooth'] / df_pp['heartrate_smooth']
            
            df_pp['pp_smooth'] = df_pp['pulse_power'].rolling(window=12, center=True).mean() 
            x_pp = df_pp['time_min']
            y_pp = df_pp['pulse_power']
            valid_idx = np.isfinite(x_pp) & np.isfinite(y_pp)
            
            if valid_idx.sum() > 100:
                slope_pp, intercept_pp, _, _, _ = stats.linregress(x_pp[valid_idx], y_pp[valid_idx])
                trend_line_pp = intercept_pp + slope_pp * x_pp
                total_drop = (trend_line_pp.iloc[-1] - trend_line_pp.iloc[0]) / trend_line_pp.iloc[0] * 100
            else:
                slope_pp = 0; total_drop = 0; trend_line_pp = None

            avg_pp = df_pp['pulse_power'].mean()
            
            c_pp1, c_pp2, c_pp3 = st.columns(3)
            c_pp1.metric("Średnie Pulse Power", f"{avg_pp:.2f} W/bpm", help="Ile watów generuje jedno uderzenie serca.")
            
            drift_color = "normal"
            if total_drop < -5: drift_color = "inverse"
            
            c_pp2.metric("Zmiana Efektywności (Trend)", f"{total_drop:.1f}%", delta_color=drift_color)
            c_pp3.metric("Interpretacja", "Stabilna Wydolność" if total_drop > -5 else "Dryf / Zmęczenie")

            fig_pp = go.Figure()
            
            fig_pp.add_trace(go.Scatter(
                x=df_pp['time_min'], 
                y=df_pp['pp_smooth'], 
                customdata=df_pp['watts_smooth'],
                name='Pulse Power (W/bpm)', 
                mode='lines',
                line=dict(color='#FFD700', width=2),
                hovertemplate="Pulse Power: %{y:.2f} W/bpm<br>Moc: %{customdata:.0f} W<extra></extra>"
            ))
            
            if trend_line_pp is not None:
                fig_pp.add_trace(go.Scatter(
                    x=x_pp, y=trend_line_pp,
                    name='Trend',
                    mode='lines',
                    line=dict(color='white', width=1.5, dash='dash'),
                    hoverinfo='skip'
                ))
            
            fig_pp.add_trace(go.Scatter(
                x=df_pp['time_min'], y=df_pp['watts_smooth'],
                name='Moc (tło)',
                yaxis='y2',
                line=dict(width=0),
                fill='tozeroy',
                fillcolor='rgba(255,255,255,0.05)',
                hoverinfo='skip'
            ))

            fig_pp.update_layout(
                template="plotly_dark",
                title="Pulse Power: Koszt Energetyczny Serca",
                hovermode="x unified",
                xaxis=dict(
                    title="Czas [min]",
                    tickformat=".0f",
                    hoverformat=".0f"
                ),
                yaxis=dict(title="Pulse Power [W / bpm]"),
                yaxis2=dict(overlaying='y', side='right', showgrid=False, visible=False),
                margin=dict(l=10, r=10, t=40, b=10),
                legend=dict(orientation="h", y=1.05, x=0),
                height=450
            )
            
            st.plotly_chart(fig_pp, use_container_width=True)
            
            st.info("""
            **💡 Jak to czytać?**
            
            * **Pulse Power (W/bpm)** mówi nam o objętości wyrzutowej serca i ekstrakcji tlenu. Im wyżej, tym lepiej.
            * **Trend Płaski:** Idealnie. Twoje serce pracuje tak samo wydajnie w 1. minucie jak w 60. minucie. Jesteś dobrze nawodniony i chłodzony.
            * **Trend Spadkowy (Dryf):** Serce musi bić coraz szybciej, żeby utrzymać te same waty.
                * **Spadek < 5%:** Norma fizjologiczna.
                * **Spadek > 10%:** Odwodnienie, przegrzanie lub wyczerpanie zapasów glikogenu w mięśniach. Czas zjeść i pić!
            """)
        else:
            st.warning("Zbyt mało danych (jazda poniżej 50W lub HR poniżej 90bpm), aby obliczyć wiarygodne Pulse Power.")
    else:
        st.error("Brak danych mocy lub tętna.")
        
    # =========================================================================
    # SEKCJA: GROSS EFFICIENCY
    # =========================================================================
    st.divider()
    st.subheader("⚙️ Gross Efficiency (GE%) - Estymacja")
    st.caption("Stosunek mocy generowanej (Waty) do spalanej energii (Metabolizm). Typowo: 18-23%.")

    # Sprawdź czy mamy dostęp do parametrów zawodnika
    rider_weight = st.session_state.get('rider_weight', 75.0)
    rider_age = st.session_state.get('rider_age', 30)
    is_male = st.session_state.get('is_male', True)

    if 'watts_smooth' in df_plot_resampled.columns and 'heartrate_smooth' in df_plot_resampled.columns:
        import numpy as np
        
        # Współczynniki Keytela
        gender_factor = -55.0969 if is_male else -20.4022
        
        # Obliczenie wydatku energetycznego (EE) w kJ/min
        ee_kj_min = gender_factor + \
                    (0.6309 * df_plot_resampled['heartrate_smooth']) + \
                    (0.1988 * rider_weight) + \
                    (0.2017 * rider_age)
        
        # Konwersja na Waty Metaboliczne
        p_metabolic = (ee_kj_min * 1000) / 60
        p_metabolic = p_metabolic.replace(0, np.nan)
        
        # Obliczamy Gross Efficiency
        ge_series = (df_plot_resampled['watts_smooth'] / p_metabolic) * 100
        
        # Filtrujemy dane nierealistyczne
        mask_ge = (df_plot_resampled['watts_smooth'] > 100) & \
                (ge_series > 5) & (ge_series < 30) & \
                (df_plot_resampled['heartrate_smooth'] > 110) 
        
        df_ge = pd.DataFrame({
            'time_min': df_plot_resampled['time_min'],
            'ge': ge_series,
            'watts': df_plot_resampled['watts_smooth']
        })
        df_ge.loc[~mask_ge, 'ge'] = np.nan

        if not df_ge['ge'].isna().all():
            avg_ge = df_ge['ge'].mean()
            
            cg1, cg2, cg3 = st.columns(3)
            cg1.metric("Średnie GE", f"{avg_ge:.1f}%", help="Pro: 23%+, Amator: 18-21%")
            
            valid_ge = df_ge.dropna(subset=['ge'])
            if len(valid_ge) > 100:
                from scipy import stats
                slope_ge, _, _, _, _ = stats.linregress(valid_ge['time_min'], valid_ge['ge'])
                total_drift_ge = slope_ge * (valid_ge['time_min'].iloc[-1] - valid_ge['time_min'].iloc[0])
                cg2.metric("Zmiana GE (Trend)", f"{total_drift_ge:.1f}%", delta_color="inverse" if total_drift_ge < 0 else "normal")
            else:
                cg2.metric("Zmiana GE", "-")

            cg3.info("Wartości powyżej 25% mogą wynikać z opóźnienia tętna względem mocy (np. krótkie interwały). Analizuj trendy na długich odcinkach.")

            fig_ge = go.Figure()
            
            fig_ge.add_trace(go.Scatter(
                x=df_ge['time_min'], 
                y=df_ge['ge'],
                customdata=df_ge['watts'],
                mode='lines',
                name='Gross Efficiency (%)',
                line=dict(color='#00cc96', width=1.5),
                connectgaps=False,
                hovertemplate="GE: %{y:.1f}%<br>Moc: %{customdata:.0f} W<extra></extra>"
            ))
            
            fig_ge.add_trace(go.Scatter(
                x=df_ge['time_min'], 
                y=df_ge['watts'],
                mode='lines',
                name='Moc (Tło)',
                yaxis='y2',
                line=dict(color='rgba(255,255,255,0.1)', width=1),
                fill='tozeroy',
                fillcolor='rgba(255,255,255,0.05)',
                hoverinfo='skip'
            ))
            
            if len(valid_ge) > 100:
                trend_line = np.poly1d(np.polyfit(valid_ge['time_min'], valid_ge['ge'], 1))(valid_ge['time_min'])
                fig_ge.add_trace(go.Scatter(
                    x=valid_ge['time_min'],
                    y=trend_line,
                    mode='lines',
                    name='Trend GE',
                    line=dict(color='white', width=2, dash='dash')
                ))

            fig_ge.update_layout(
                template="plotly_dark",
                title="Efektywność Brutto (GE%) w Czasie",
                hovermode="x unified",
                xaxis=dict(
                    title="Czas [min]",
                    tickformat=".0f",
                    hoverformat=".0f"
                ),
                yaxis=dict(title="GE [%]", range=[10, 30]),
                yaxis2=dict(title="Moc [W]", overlaying='y', side='right', showgrid=False),
                height=400,
                margin=dict(l=10, r=10, t=40, b=10),
                legend=dict(orientation="h", y=1.1, x=0)
            )
            
            st.plotly_chart(fig_ge, use_container_width=True)
            
            with st.expander("🧠 Jak interpretować GE?", expanded=False):
                st.markdown("""
                **Fizjologia GE:**
                * **< 18%:** Niska wydajność. Dużo energii tracisz na ciepło i nieskoordynowane ruchy (kołysanie biodrami). Częste u początkujących.
                * **19-21%:** Standard amatorski. Dobrze wytrenowany kolarz klubowy.
                * **22-24%:** Poziom ELITE / PRO. Twoje mięśnie to maszyny.
                * **> 25%:** Podejrzane (chyba że jesteś zwycięzcą Tour de France). Często wynika z błędów pomiaru (np. miernik mocy zawyża, tętno zaniżone, jazda w dół).

                **Dlaczego GE spada w czasie?**
                Gdy się męczysz, rekrutujesz włókna mięśniowe typu II (szybkokurczliwe), które są mniej wydajne tlenowo. Dodatkowo rośnie temperatura ciała (Core Temp), co kosztuje energię. Spadek GE pod koniec długiego treningu to doskonały wskaźnik zmęczenia metabolicznego.
                """)
        else:
            st.warning("Brak wystarczających danych do obliczenia GE (zbyt krótkie odcinki stabilnej jazdy).")
    else:
        st.error("Do obliczenia GE potrzebujesz danych Mocy (Watts) oraz Tętna (HR).")


