import streamlit as st
import pandas as pd
import numpy as np
import os
import re
import fuzzywuzzy
import sys
import io
import logging
import concurrent.futures
import difflib
from fuzzywuzzy import process
from re import findall
from io import StringIO
from espn_api.football import League

# Set logging level to WARNING
logging.getLogger('espn_api').setLevel(logging.WARNING)

# Redirect stdout to capture the output
old_stdout = sys.stdout
sys.stdout = io.StringIO()

# Get the captured output
output_text = sys.stdout.getvalue()

# Reset stdout
sys.stdout = old_stdout

###################
##### Sidebar #####
###################
# st.sidebar.image('ffa_red.png', use_column_width=True)
st.sidebar.markdown(" ## About This App:")
st.sidebar.markdown("This is a trade calculator for those of you playing in ESPN leagues!")

st.sidebar.markdown("## Read This!")
st.sidebar.markdown("SWID and ESPN_S2 will be the most confusing values to find. I know it's going to look difficult, but I've provided a video showing you exactly how to find them. These values also will not change. So you can save them once you find them. That way you only need to go through the process of finding them once. After that the tool is very self explanatory, but I'll make another video detailing how to use it below as well")
st.sidebar.markdown("[Click this link to help with collecting your league data](https://www.youtube.com/watch?v=LLSQsDuFdiY)")
st.sidebar.markdown("[Click this link for a breakdown of how to use the trade calculator](https://www.youtube.com/watch?v=LLSQsDuFdiY)")
st.sidebar.markdown("[Click this link to access the ROS rankings from week 14](https://www.thefantasyfootballadvice.com/ros-rankings-for-trade-calculator/)")

@st.cache_data
def fetch_league_data(league_id, year, swid, espn_s2):
    with st.spinner("Fetching league data..."):
        league = League(league_id, year, swid=swid, espn_s2=espn_s2)
        draft = league.draft
        standings = league.standings()
        settings = league.settings
        team_count = settings.team_count
        teams = league.teams
        qb_fa = league.free_agents(position="QB")
        rb_fa = league.free_agents(position="RB")
        wr_fa = league.free_agents(position="WR")
        te_fa = league.free_agents(position="TE")
        k_fa = league.free_agents(position="K")
        dst_fa = league.free_agents(position="D/ST")
    return draft, standings, settings, team_count, teams, qb_fa, rb_fa, wr_fa, te_fa, k_fa, dst_fa

tab_scrape, tab_inputs, tab_trade = st.tabs(["Collect League", "Input Settings", "Trade Calculator"])

with tab_scrape:
    # User needs to input these values
    league_id = st.number_input("Input League ID", value=0)
    year = st.number_input("Input Year (Use 2023 for last season...2024 for a league that drafted in 2024)", value=2023)
    swid = st.text_input("Input swid (Watch the video on the sidebar to learn how to find this)", value="")
    espn_s2 = st.text_input("Input espn_s2 (Watch the video on the sidebar to learn how to find this)", value="")

    st.header("Upload ROS Rankings Here :point_down:")
    uploaded_file = st.file_uploader("Choose a file")
    if uploaded_file is not None:
        # To read file as bytes:
        bytes_data = uploaded_file.getvalue()

        # Can be used wherever a "file-like" object is accepted:
        ros = pd.read_csv(uploaded_file)

        # Keep these columns of ros
        ros = ros[["Player Name", "Team", "Pos", "PPR", "HPPR", "Std", "1.5 TE", "6 Pt Pass", "DK"]]

        if st.checkbox("Collect League Data (do not check until you fill out the 5 values above)"):
            # This will collect the stats we need!
            if league_id != 0 and year != 0 and swid != "" and espn_s2 != "":
                draft, standings, settings, team_count, teams, qb_fa, rb_fa, wr_fa, te_fa, k_fa, dst_fa = fetch_league_data(league_id, year, swid, espn_s2)

with tab_inputs:
    # Select Scoring Format
    scoring = st.selectbox(
        "What is your league's scoring format?",
        ('PPR', 'HPPR', 'Std', '1.5 TE', '6 Pt Pass', 'DK'))


    ########################################
    ##### Input Starting Roster Format #####
    ########################################

    s_qbs = st.number_input('Starting QB Roster Spots', min_value = 0, step = 1)
    s_rbs = st.number_input('Starting RB Roster Spots', min_value = 0, step = 1)
    s_wrs = st.number_input('Starting WR Roster Spots', min_value = 0, step = 1)
    s_tes = st.number_input('Starting TE Roster Spots', min_value = 0, step = 1)
    s_flex = st.number_input('Starting FLEX Roster Spots', min_value = 0, step = 1)
    s_sflex = st.number_input('Starting Super FLEX Roster Spots', min_value = 0, step = 1)
    s_ks = st.number_input('Starting K Roster Spots', min_value = 0, step = 1)
    s_dsts = st.number_input('Starting D/ST Roster Spots', min_value = 0, step = 1)
    s_bench = st.number_input('Bench Spots', min_value = 0, step = 1)
    
    
# Function to find the best match for each player
@st.cache_data(ttl=600)  # Set the time-to-live (TTL) to 600 seconds (adjust as needed)
def find_best_match(player_name, choices):
    return process.extractOne(player_name, choices)

with tab_trade:
    
    team_list = []
    rosters_list = []

    for i in range(len(teams)):
        team = teams[i]
        roster = teams[i].roster
        team_list.append(team)
        rosters_list.append(roster)

    # Extract team name
    cleaned_teams = [f"{team}".replace("Team(", "").replace(")", "") for team in team_list]
    # Extract player name
    cleaned_players = [[str(player).replace("Player(", "").replace(")", "") for player in sublist] for sublist in rosters_list]

    # Create a DF where each column is a team in the league
    final_rosters_df = pd.DataFrame(cleaned_players).astype(str).T
    final_rosters_df.columns = cleaned_teams
    teams_list = final_rosters_df.columns.tolist()

    # Select your team and trade partner
    my_team = st.selectbox("Select Your Team", options = teams_list)
    trade_partner = st.selectbox("Select Trade Partner's Team", options = teams_list)

    # Create My Team
    my_team_df = final_rosters_df[[my_team]]
    my_team_df.columns = ["Player Name"]

    # Create Trade Partner
    trade_partner_df = final_rosters_df[[trade_partner]]
    trade_partner_df.columns = ["Player Name"]

    #################################################
    ########## My Team and Opponent Values ##########
    #################################################

    # Find best matches for each player in my_team_df
    my_team_df['Best Match'] = my_team_df['Player Name'].apply(lambda x: find_best_match(x, ros['Player Name']))

    # Split the result into matched and unmatched
    my_team_df['Matched'] = my_team_df['Best Match'].apply(lambda x: x[0] if x[1] >= 85 else None)
    my_team_df['Unmatched'] = my_team_df['Player Name'][~my_team_df['Matched'].notna()]

    # Merge matched players based on the best match
    my_team_values = my_team_df.merge(ros, left_on='Matched', right_on='Player Name', how='left')

    # Just keep certain columns
    # my_team_values = my_team_values[["Player Name_y", "Team", "Pos", "PPR", "HPPR", "Standard", "TE Premium", "6 Pt Pass"]]

    # Rename Column
    my_team_values = my_team_values.rename(columns={'Player Name_y': 'Player Name'})

    # Display the merged DataFrame
    my_team_values = my_team_values[["Player Name", "Team", "Pos", "PPR", "HPPR", "Std", "1.5 TE", "6 Pt Pass", "DK"]]
    
    # Add in a "New Pos" feature that's just pos
    my_team_values["New Pos"] = my_team_values["Pos"]

    ######################################
    ########## Opponents Values ##########
    ######################################

    # Find best matches for each player in my_team_df
    trade_partner_df['Best Match'] = trade_partner_df['Player Name'].apply(lambda x: find_best_match(x, ros['Player Name']))

    # Split the result into matched and unmatched
    trade_partner_df['Matched'] = trade_partner_df['Best Match'].apply(lambda x: x[0] if x[1] >= 85 else None)
    trade_partner_df['Unmatched'] = trade_partner_df['Player Name'][~trade_partner_df['Matched'].notna()]

    # Merge matched players based on the best match
    trade_partner_values = trade_partner_df.merge(ros, left_on='Matched', right_on='Player Name', how='left')

    # Just keep certain columns
    # my_team_values = my_team_values[["Player Name_y", "Team", "Pos", "PPR", "HPPR", "Standard", "TE Premium", "6 Pt Pass"]]

    # Rename Column
    trade_partner_values = trade_partner_values.rename(columns={'Player Name_y': 'Player Name'})

    # Display the merged DataFrame
    trade_partner_values = trade_partner_values[["Player Name", "Team", "Pos", "PPR", "HPPR", "Std", "1.5 TE", "6 Pt Pass", "DK"]]

    # Add in a "New Pos" feature that's just pos
    trade_partner_values["New Pos"] = trade_partner_values["Pos"]

    #######################################################
    ########## Calculate total for each position ##########
    #######################################################

    # My Team
    qbs = len(my_team_values[my_team_values['Pos'] == "QB"])
    rbs = len(my_team_values[my_team_values['Pos'] == "RB"])
    wrs = len(my_team_values[my_team_values['Pos'] == "WR"])
    tes = len(my_team_values[my_team_values['Pos'] == "TE"])
    ks = len(my_team_values[my_team_values['Pos'] == "K"])
    dsts = len(my_team_values[my_team_values['Pos'] == "D/ST"])

    # Trade Partner
    t_qbs = len(trade_partner_values[trade_partner_values['Pos'] == "QB"])
    t_rbs = len(trade_partner_values[trade_partner_values['Pos'] == "RB"])
    t_wrs = len(trade_partner_values[trade_partner_values['Pos'] == "WR"])
    t_tes = len(trade_partner_values[trade_partner_values['Pos'] == "TE"])
    t_ks = len(trade_partner_values[trade_partner_values['Pos'] == "K"])
    t_dsts = len(trade_partner_values[trade_partner_values['Pos'] == "D/ST"])
    
    #######################################
    ########## Creating Starters ##########
    #######################################

    # Creating Pos Starters
    starting_qbs = my_team_values[my_team_values['Pos'] == "QB"].sort_values(by = scoring, ascending = False)[0:s_qbs]
    starting_rbs = my_team_values[my_team_values['Pos'] == "RB"].sort_values(by = scoring, ascending = False)[0:s_rbs]
    starting_wrs = my_team_values[my_team_values['Pos'] == "WR"].sort_values(by = scoring, ascending = False)[0:s_wrs]
    starting_tes = my_team_values[my_team_values['Pos'] == "TE"].sort_values(by = scoring, ascending = False)[0:s_tes]
    starting_ks = my_team_values[my_team_values['Pos'] == "K"].sort_values(by = scoring, ascending = False)[0:s_ks]
    starting_dsts = my_team_values[my_team_values['Pos'] == "D/ST"].sort_values(by = scoring, ascending = False)[0:s_dsts]

    # Create FLEX Starters
    flex_viable_rbs = my_team_values[my_team_values['Pos'] == "RB"].sort_values(by = scoring, ascending = False)[s_rbs:rbs]
    flex_viable_wrs = my_team_values[my_team_values['Pos'] == "WR"].sort_values(by = scoring, ascending = False)[s_wrs:wrs]
    flex_viable_tes = my_team_values[my_team_values['Pos'] == "TE"].sort_values(by = scoring, ascending = False)[s_tes:tes]
    starting_flex = pd.concat([flex_viable_rbs, flex_viable_wrs, flex_viable_tes]).sort_values(by = scoring, ascending = False)[0:s_flex]
    starting_flex["New Pos"] = "FLEX"

    # Create SuperFlex
    superflex_viable_qbs = my_team_values[my_team_values['Pos'] == "QB"].sort_values(by = scoring, ascending = False)[s_qbs:qbs]
    starting_superflex = pd.concat([superflex_viable_qbs, starting_flex[s_flex:]])[0:s_sflex]
    starting_superflex["New Pos"] = "SuperFlex"
    final_starters = pd.concat([starting_qbs, starting_rbs, starting_wrs, starting_tes, starting_flex, starting_superflex, starting_dsts]).reset_index(drop=True)
    final_starters = final_starters[["Pos", "New Pos", "Player Name", scoring]]    

    # Create Bench
    my_team_values = my_team_values[["Pos","New Pos", "Player Name", scoring]]  
    bench_df = pd.concat([final_starters, my_team_values])
    bench_df = bench_df.drop_duplicates(subset = ["Player Name", scoring], keep=False)

    ##################################################
    ########## Opponents Starters and Bench ##########
    ##################################################

    # Creating Pos Starters
    trade_partner_starting_qbs = trade_partner_values[trade_partner_values['Pos'] == "QB"].sort_values(by = scoring, ascending = False)[0:s_qbs]
    trade_partner_starting_rbs = trade_partner_values[trade_partner_values['Pos'] == "RB"].sort_values(by = scoring, ascending = False)[0:s_rbs]
    trade_partner_starting_wrs = trade_partner_values[trade_partner_values['Pos'] == "WR"].sort_values(by = scoring, ascending = False)[0:s_wrs]
    trade_partner_starting_tes = trade_partner_values[trade_partner_values['Pos'] == "TE"].sort_values(by = scoring, ascending = False)[0:s_tes]
    trade_partner_starting_ks = trade_partner_values[trade_partner_values['Pos'] == "K"].sort_values(by = scoring, ascending = False)[0:s_ks]
    trade_partner_starting_dsts = trade_partner_values[trade_partner_values['Pos'] == "D/ST"].sort_values(by = scoring, ascending = False)[0:s_dsts]

    # Create FLEX Starters
    trade_partner_flex_viable_rbs = trade_partner_values[trade_partner_values['Pos'] == "RB"].sort_values(by = scoring, ascending = False)[s_rbs:t_rbs]
    trade_partner_flex_viable_wrs = trade_partner_values[trade_partner_values['Pos'] == "WR"].sort_values(by = scoring, ascending = False)[s_wrs:t_wrs]
    trade_partner_flex_viable_tes = trade_partner_values[trade_partner_values['Pos'] == "TE"].sort_values(by = scoring, ascending = False)[s_tes:t_tes]
    trade_partner_starting_flex = pd.concat([trade_partner_flex_viable_rbs, trade_partner_flex_viable_wrs, trade_partner_flex_viable_tes]).sort_values(by = scoring, ascending = False)[0:s_flex]
    trade_partner_starting_flex["New Pos"] = "FLEX"

    # Create SuperFlex
    trade_partner_superflex_viable_qbs = trade_partner_values[trade_partner_values['Pos'] == "QB"].sort_values(by = scoring, ascending = False)[s_qbs:t_qbs]
    trade_partner_starting_superflex = pd.concat([trade_partner_superflex_viable_qbs, trade_partner_starting_flex[s_flex:]])[0:s_sflex]
    trade_partner_starting_superflex["New Pos"] = "SuperFlex"
    trade_partner_final_starters = pd.concat([trade_partner_starting_qbs, trade_partner_starting_rbs, trade_partner_starting_wrs, trade_partner_starting_tes,
                                              trade_partner_starting_flex, trade_partner_starting_superflex, trade_partner_starting_dsts]).reset_index(drop=True)
    trade_partner_final_starters = trade_partner_final_starters[["Pos","New Pos", "Player Name", scoring]]    

    # Create Bench
    trade_partner_values = trade_partner_values[["Pos","New Pos", "Player Name", scoring]]  
    trade_partner_bench_df = pd.concat([trade_partner_final_starters, trade_partner_values])
    trade_partner_bench_df = trade_partner_bench_df.drop_duplicates(subset = ["Player Name", scoring], keep=False)
    
    ############################################
    ########## Calculate Adjusted PPG ##########
    ############################################

    ### Calculate Total Roster Adjusted PPG ###
    if (s_qbs+s_rbs+s_wrs+s_tes+s_flex+s_sflex+s_ks+s_dsts) == 0:
        qb_weight = 0
        rb_weight = 0
        wr_weight = 0
        te_weight = 0
        k_weight = 0
        dst_weight = 0
    else:
        qb_weight = (s_qbs+s_sflex)/(s_qbs+s_rbs+s_wrs+s_tes+s_flex+s_sflex+s_ks+s_dsts)
        rb_weight = (s_rbs+s_flex+s_sflex)/(s_qbs+s_rbs+s_wrs+s_tes+s_flex+s_sflex+s_ks+s_dsts)
        wr_weight = (s_wrs+s_flex+s_sflex)/(s_qbs+s_rbs+s_wrs+s_tes+s_flex+s_sflex+s_ks+s_dsts)
        te_weight = (s_tes+s_flex+s_sflex)/(s_qbs+s_rbs+s_wrs+s_tes+s_flex+s_sflex+s_ks+s_dsts)
        k_weight = (s_ks)/(s_qbs+s_rbs+s_wrs+s_tes+s_flex+s_sflex+s_ks+s_dsts)
        dst_weight = (s_dsts)/(s_qbs+s_rbs+s_wrs+s_tes+s_flex+s_sflex+s_ks+s_dsts)

    # Create df with those weights
    all_weights = pd.DataFrame(
    {"Pos": ["QB", "RB", "WR", "TE", "K", "D/ST"],
        "Weight": [qb_weight, rb_weight, wr_weight, te_weight, k_weight, dst_weight]})  

    # Merge weights into bench_df
    bench_weights_df = bench_df.merge(all_weights, on = "Pos")
    bench_weights_df["Weighted PPG"] = bench_weights_df[scoring]*bench_weights_df["Weight"]

    # Divide each of those weights by the number on the bench
    qbs_on_bench = bench_weights_df[bench_weights_df["Pos"] == "QB"].shape[0]
    rbs_on_bench = bench_weights_df[bench_weights_df["Pos"] == "RB"].shape[0]
    wrs_on_bench = bench_weights_df[bench_weights_df["Pos"] == "WR"].shape[0]
    tes_on_bench = bench_weights_df[bench_weights_df["Pos"] == "TE"].shape[0]
    ks_on_bench = bench_weights_df[bench_weights_df["Pos"] == "K"].shape[0]
    dsts_on_bench = bench_weights_df[bench_weights_df["Pos"] == "D/ST"].shape[0]

    # Adjust weights to reflect that number
    if qbs_on_bench != 0:
        adj_qb_weight = qb_weight/qbs_on_bench
    else:
        adj_qb_weight = 0

    if rbs_on_bench != 0:
        adj_rb_weight = rb_weight/rbs_on_bench
    else:
        adj_rb_weight = 0        

    if wrs_on_bench != 0:
        adj_wr_weight = wr_weight/wrs_on_bench
    else:
        adj_wr_weight = 0

    if tes_on_bench != 0:
        adj_te_weight = te_weight/tes_on_bench
    else:
        adj_te_weight = 0

    if ks_on_bench != 0:
        adj_k_weight = k_weight/ks_on_bench
    else:
        adj_k_weight = 0

    if dsts_on_bench != 0:
        adj_dst_weight = dst_weight/dsts_on_bench
    else:
        adj_dst_weight = 0

    # Create df with those adj weights
    adj_weights = pd.DataFrame(
    {"Pos": ["QB", "RB", "WR", "TE", "K", "D/ST"],
        "Weight": [adj_qb_weight, adj_rb_weight, adj_wr_weight, adj_te_weight, adj_k_weight, adj_dst_weight]}) 

    # Merge weights into bench_df
    adj_bench_weights_df = bench_df.merge(adj_weights, on = "Pos")
    adj_bench_weights_df["Weighted PPG"] = adj_bench_weights_df[scoring]*adj_bench_weights_df["Weight"]
    
    #################################################
    ########## Trade Partners Adjusted PPG ##########
    #################################################

    ### Calculate Total Roster Adjusted PPG ###

    # Create df with those weights
    all_weights = pd.DataFrame(
    {"Pos": ["QB", "RB", "WR", "TE", "K", "D/ST"],
        "Weight": [qb_weight, rb_weight, wr_weight, te_weight, k_weight, dst_weight]})  

    # Merge weights into bench_df
    trade_partner_bench_weights_df = trade_partner_bench_df.merge(all_weights, on = "Pos")
    trade_partner_bench_weights_df["Weighted PPG"] = trade_partner_bench_weights_df[scoring]*trade_partner_bench_weights_df["Weight"]

    # Divide each of those weights by the number on the bench
    qbs_on_bench = trade_partner_bench_weights_df[trade_partner_bench_weights_df["Pos"] == "QB"].shape[0]
    rbs_on_bench = trade_partner_bench_weights_df[trade_partner_bench_weights_df["Pos"] == "RB"].shape[0]
    wrs_on_bench = trade_partner_bench_weights_df[trade_partner_bench_weights_df["Pos"] == "WR"].shape[0]
    tes_on_bench = trade_partner_bench_weights_df[trade_partner_bench_weights_df["Pos"] == "TE"].shape[0]
    ks_on_bench = trade_partner_bench_weights_df[trade_partner_bench_weights_df["Pos"] == "K"].shape[0]
    dsts_on_bench = trade_partner_bench_weights_df[trade_partner_bench_weights_df["Pos"] == "D/ST"].shape[0]

    # Adjust weights to reflect that number
    if qbs_on_bench != 0:
        adj_qb_weight = qb_weight/qbs_on_bench
    else:
        adj_qb_weight = 0

    if rbs_on_bench != 0:
        adj_rb_weight = rb_weight/rbs_on_bench
    else:
        adj_rb_weight = 0        

    if wrs_on_bench != 0:
        adj_wr_weight = wr_weight/wrs_on_bench
    else:
        adj_wr_weight = 0

    if tes_on_bench != 0:
        adj_te_weight = te_weight/tes_on_bench
    else:
        adj_te_weight = 0

    if ks_on_bench != 0:
        adj_k_weight = k_weight/ks_on_bench
    else:
        adj_k_weight = 0

    if dsts_on_bench != 0:
        adj_dst_weight = dst_weight/dsts_on_bench
    else:
        adj_dst_weight = 0

    # Create df with those adj weights
    adj_weights = pd.DataFrame(
    {"Pos": ["QB", "RB", "WR", "TE", "K", "D/ST"],
        "Weight": [adj_qb_weight, adj_rb_weight, adj_wr_weight, adj_te_weight, adj_k_weight, adj_dst_weight]}) 

    # Merge weights into bench_df
    trade_partner_adj_bench_weights_df = trade_partner_bench_df.merge(adj_weights, on = "Pos")
    trade_partner_adj_bench_weights_df["Weighted PPG"] = trade_partner_adj_bench_weights_df[scoring]*trade_partner_adj_bench_weights_df["Weight"]

    # Adjusted PPG!
    og_score = round(final_starters[scoring].sum() + adj_bench_weights_df['Weighted PPG'].sum(),2)
    st.write("My Team's Adjusted PPG: ", og_score)
    st.write("Trade Partner's Adjusted PPG: ", round(trade_partner_final_starters[scoring].sum() + trade_partner_adj_bench_weights_df['Weighted PPG'].sum(),2))
    
    # Combine starters and bench
    my_roster = [*final_starters['Player Name'], *adj_bench_weights_df['Player Name']]
    opponents_roster = [*trade_partner_final_starters['Player Name'], *trade_partner_adj_bench_weights_df['Player Name']]
    
    # Make a drop down for each team's roster
    my_team_list = st.multiselect(
        "Player's You're Trading AWAY",
        my_roster)
    
    opponents_roster_list = st.multiselect(
        "Player's You're Trading FOR",
        opponents_roster)
    
    # This is the new team...before adding in the other players
    my_new_team = [x for x in my_roster if x not in my_team_list]
    opponent_new_team = [x for x in opponents_roster if x not in opponents_roster_list]
    
    # Now we add the player's we're trading for to the list
    my_new_team2 = [*my_new_team, *opponents_roster_list]
    opponent_new_team2 = [*opponent_new_team, *my_team_list]
       
    # Now we take that list and go back to our final roster. We want to only keep rows of players that are left
    # Stack df's on top of each other
    my_dfs = [final_starters, adj_bench_weights_df]
    my_og_roster = pd.concat(my_dfs).reset_index(drop=True)
    left_on_my_roster = my_og_roster[my_og_roster['Player Name'].isin(my_new_team2)]
    
    # Next create a subset of the opponents team with the players you're getting
    opponent_dfs = [trade_partner_final_starters, trade_partner_adj_bench_weights_df]
    opponent_og_roster = pd.concat(opponent_dfs).reset_index(drop=True)
    get_from_opponent = opponent_og_roster[opponent_og_roster['Player Name'].isin(opponents_roster_list)]

    # Then stack those two DF's!
    my_post_trade_roster = pd.concat([left_on_my_roster, get_from_opponent])
    my_post_trade_roster = my_post_trade_roster[["Pos", "Player Name", scoring]]
    
    # Do the same for the opponent
    # Stack df's on top of each other
    opponent_dfs = [trade_partner_final_starters, trade_partner_adj_bench_weights_df]
    opponent_og_roster = pd.concat(opponent_dfs).reset_index(drop=True)
    left_on_opponent_roster = opponent_og_roster[opponent_og_roster['Player Name'].isin(opponent_new_team2)]
    
    # Next create a subset of the opponents team with the players you're getting
    my_dfs = [final_starters, adj_bench_weights_df]
    my_og_roster = pd.concat(my_dfs).reset_index(drop=True)
    get_from_me = my_og_roster[my_og_roster['Player Name'].isin(my_team_list)]

    # Then stack those two DF's!
    opponent_post_trade_roster = pd.concat([left_on_opponent_roster, get_from_me])
    opponent_post_trade_roster = opponent_post_trade_roster[["Pos", "Player Name", scoring]]
    

    # Add in a "New Pos" feature that's just pos to each
    my_post_trade_roster["New Pos"] = my_post_trade_roster["Pos"]
    opponent_post_trade_roster["New Pos"] = opponent_post_trade_roster["Pos"]
    
    def extract_player_name(player):
    # Remove "Player(" from the beginning and extract the player name
        player_name = re.sub(r'^Player\((.*?)\)', r'\1', str(player))
        return re.match(r"^(.*?), points", player_name).group(1)

    def find_best_match_simple(player_name, choices):
        # Get the best match using simple string matching
        matches = difflib.get_close_matches(player_name, choices, n=1, cutoff=0.85)

        # Return the best match and its similarity score
        if matches:
            return matches[0], difflib.SequenceMatcher(None, player_name, matches[0]).ratio()
        else:
            return None, 0.0

    # Create a DF that has the free agents
    fa_list = qb_fa + rb_fa + wr_fa + te_fa + k_fa + dst_fa

    # Replace string manipulation with a function
    fa_df = pd.DataFrame({'Player Name': [extract_player_name(player) for player in fa_list]})

    # Find best matches for each player in my_team_df using the simple method
    fa_df['Best Match'] = fa_df['Player Name'].apply(lambda x: find_best_match_simple(x, ros['Player Name']))

    # Split the result into matched and unmatched
    fa_df['Matched'] = fa_df['Best Match'].apply(lambda x: x[0] if x[1] >= .85 else None)
    fa_df['Unmatched'] = fa_df['Player Name'][~fa_df['Matched'].notna()]

    # Merge matched players based on the best match
    fa_df_values = fa_df.merge(ros, left_on='Matched', right_on='Player Name', how='left')

    # Rename Column
    fa_df_values = fa_df_values.rename(columns={'Player Name_y': 'Player Name'})

    # Display the merged DataFrame
    fa_df_values = fa_df_values[["Player Name", "Team", "Pos", "PPR", "HPPR", "Std", "1.5 TE", "6 Pt Pass", "DK"]]

    # Sort by scoring
    fa_df_values = fa_df_values.sort_values(by=scoring, ascending=False)
    # st.dataframe(fa_df_values)

    # Select the position you wish to add off FA
    fa_pos = st.multiselect("Which Position Do You Want to Add?",
                           ["QB", "RB", "WR", "TE", "K", "D/ST"])

    # Have that list as an option to multiselect for each position
    if fa_pos is not None:
        fa_add = st.multiselect("Pick player(s) to ADD",
                                fa_df_values[fa_df_values['Pos'].isin(fa_pos)]['Player Name'])
        
    team_drop = st.multiselect("Pick player(s) to DROP",
                              my_post_trade_roster['Player Name'])
    

    # Make those two adjustments to your team
    my_post_trade_roster = pd.concat([my_post_trade_roster, fa_df_values[fa_df_values['Player Name'].isin(fa_add)]])
    my_post_trade_roster = my_post_trade_roster[~my_post_trade_roster['Player Name'].isin(team_drop)]
    
    # Signal if your team is the correct number of people
    players_to_adjust = (len(fa_add) + len(opponents_roster_list)) - (len(team_drop) + len(my_team_list))

    if players_to_adjust > 0:
        action = "Drop or Trade Away"
        st.subheader(f":red[{action} {players_to_adjust} More Player{'s' if players_to_adjust != 1 else ''}]")
    elif players_to_adjust < 0:
        action = "Add or Trade For"
        st.subheader(f":red[{action} {abs(players_to_adjust)} More Player{'s' if abs(players_to_adjust) != 1 else ''}]")
    else:
        st.subheader(":green[Add or Trade For 0 More Players]")

    ##############################################################
    ########## Now we need to recalculate adjusted PPG! ##########
    ##############################################################
    
    
    #######################################################
    ########## Calculate total for each position ##########
    #######################################################

    # My Team
    qbs = len(my_post_trade_roster[my_post_trade_roster['Pos'] == "QB"])
    rbs = len(my_post_trade_roster[my_post_trade_roster['Pos'] == "RB"])
    wrs = len(my_post_trade_roster[my_post_trade_roster['Pos'] == "WR"])
    tes = len(my_post_trade_roster[my_post_trade_roster['Pos'] == "TE"])
    ks = len(my_post_trade_roster[my_post_trade_roster['Pos'] == "K"])
    dsts = len(my_post_trade_roster[my_post_trade_roster['Pos'] == "D/ST"])

    # Trade Partner
    t_qbs = len(opponent_post_trade_roster[opponent_post_trade_roster['Pos'] == "QB"])
    t_rbs = len(opponent_post_trade_roster[opponent_post_trade_roster['Pos'] == "RB"])
    t_wrs = len(opponent_post_trade_roster[opponent_post_trade_roster['Pos'] == "WR"])
    t_tes = len(opponent_post_trade_roster[opponent_post_trade_roster['Pos'] == "TE"])
    t_ks = len(opponent_post_trade_roster[opponent_post_trade_roster['Pos'] == "K"])
    t_dsts = len(opponent_post_trade_roster[opponent_post_trade_roster['Pos'] == "D/ST"])    

    #######################################
    ########## Creating Starters ##########
    #######################################

    # Creating Pos Starters
    starting_qbs = my_post_trade_roster[my_post_trade_roster['Pos'] == "QB"].sort_values(by = scoring, ascending = False)[0:s_qbs]
    starting_rbs = my_post_trade_roster[my_post_trade_roster['Pos'] == "RB"].sort_values(by = scoring, ascending = False)[0:s_rbs]
    starting_wrs = my_post_trade_roster[my_post_trade_roster['Pos'] == "WR"].sort_values(by = scoring, ascending = False)[0:s_wrs]
    starting_tes = my_post_trade_roster[my_post_trade_roster['Pos'] == "TE"].sort_values(by = scoring, ascending = False)[0:s_tes]
    starting_ks = my_post_trade_roster[my_post_trade_roster['Pos'] == "K"].sort_values(by = scoring, ascending = False)[0:s_ks]
    starting_dsts = my_post_trade_roster[my_post_trade_roster['Pos'] == "D/ST"].sort_values(by = scoring, ascending = False)[0:s_dsts]

    # Create FLEX Starters
    flex_viable_rbs = my_post_trade_roster[my_post_trade_roster['Pos'] == "RB"].sort_values(by = scoring, ascending = False)[s_rbs:rbs]
    flex_viable_wrs = my_post_trade_roster[my_post_trade_roster['Pos'] == "WR"].sort_values(by = scoring, ascending = False)[s_wrs:wrs]
    flex_viable_tes = my_post_trade_roster[my_post_trade_roster['Pos'] == "TE"].sort_values(by = scoring, ascending = False)[s_tes:tes]
    starting_flex = pd.concat([flex_viable_rbs, flex_viable_wrs, flex_viable_tes]).sort_values(by = scoring, ascending = False)[0:s_flex]
    starting_flex["New Pos"] = "FLEX"

    # Create SuperFlex
    superflex_viable_qbs = my_post_trade_roster[my_post_trade_roster['Pos'] == "QB"].sort_values(by = scoring, ascending = False)[s_qbs:qbs]
    starting_superflex = pd.concat([superflex_viable_qbs, starting_flex[s_flex:]])[0:s_sflex]
    starting_superflex["New Pos"] = "SuperFlex"
    final_starters = pd.concat([starting_qbs, starting_rbs, starting_wrs, starting_tes, starting_flex, starting_superflex, starting_dsts]).reset_index(drop=True)
    final_starters = final_starters[["Pos", "New Pos", "Player Name", scoring]]    

    # Create Bench
    my_post_trade_roster = my_post_trade_roster[["Pos", "New Pos", "Player Name", scoring]]  
    bench_df = pd.concat([final_starters, my_post_trade_roster])
    bench_df = bench_df.drop_duplicates(subset = ["Player Name", scoring], keep=False)
    
    ##################################################
    ########## Opponents Starters and Bench ##########
    ##################################################

    # Creating Pos Starters
    trade_partner_starting_qbs = opponent_post_trade_roster[opponent_post_trade_roster['Pos'] == "QB"].sort_values(by = scoring, ascending = False)[0:s_qbs]
    trade_partner_starting_rbs = opponent_post_trade_roster[opponent_post_trade_roster['Pos'] == "RB"].sort_values(by = scoring, ascending = False)[0:s_rbs]
    trade_partner_starting_wrs = opponent_post_trade_roster[opponent_post_trade_roster['Pos'] == "WR"].sort_values(by = scoring, ascending = False)[0:s_wrs]
    trade_partner_starting_tes = opponent_post_trade_roster[opponent_post_trade_roster['Pos'] == "TE"].sort_values(by = scoring, ascending = False)[0:s_tes]
    trade_partner_starting_ks = opponent_post_trade_roster[opponent_post_trade_roster['Pos'] == "K"].sort_values(by = scoring, ascending = False)[0:s_ks]
    trade_partner_starting_dsts = opponent_post_trade_roster[opponent_post_trade_roster['Pos'] == "D/ST"].sort_values(by = scoring, ascending = False)[0:s_dsts]

    # Create FLEX Starters
    trade_partner_flex_viable_rbs = opponent_post_trade_roster[opponent_post_trade_roster['Pos'] == "RB"].sort_values(by = scoring, ascending = False)[s_rbs:t_rbs]
    trade_partner_flex_viable_wrs = opponent_post_trade_roster[opponent_post_trade_roster['Pos'] == "WR"].sort_values(by = scoring, ascending = False)[s_wrs:t_wrs]
    trade_partner_flex_viable_tes = opponent_post_trade_roster[opponent_post_trade_roster['Pos'] == "TE"].sort_values(by = scoring, ascending = False)[s_tes:t_tes]
    trade_partner_starting_flex = pd.concat([trade_partner_flex_viable_rbs, trade_partner_flex_viable_wrs, trade_partner_flex_viable_tes]).sort_values(by = scoring, ascending = False)[0:s_flex]
    trade_partner_starting_flex["New Pos"] = "FLEX"

    # Create SuperFlex
    trade_partner_superflex_viable_qbs = opponent_post_trade_roster[opponent_post_trade_roster['Pos'] == "QB"].sort_values(by = scoring, ascending = False)[s_qbs:t_qbs]
    trade_partner_starting_superflex = pd.concat([trade_partner_superflex_viable_qbs, trade_partner_starting_flex[s_flex:]])[0:s_sflex]
    trade_partner_starting_superflex["New Pos"] = "SuperFlex"
    trade_partner_final_starters = pd.concat([trade_partner_starting_qbs, trade_partner_starting_rbs, trade_partner_starting_wrs, trade_partner_starting_tes,
                                              trade_partner_starting_flex, trade_partner_starting_superflex, trade_partner_starting_dsts]).reset_index(drop=True)
    trade_partner_final_starters = trade_partner_final_starters[["Pos", "New Pos", "Player Name", scoring]]    

    # Create Bench
    trade_partner_values = opponent_post_trade_roster[["Pos", "New Pos", "Player Name", scoring]]  
    trade_partner_bench_df = pd.concat([trade_partner_final_starters, opponent_post_trade_roster])
    trade_partner_bench_df = trade_partner_bench_df.drop_duplicates(subset = ["Player Name", scoring], keep=False)
    
    ############################################
    ########## Calculate Adjusted PPG ##########
    ############################################

    ### Calculate Total Roster Adjusted PPG ###
    if (s_qbs+s_rbs+s_wrs+s_tes+s_flex+s_sflex+s_ks+s_dsts) == 0:
        qb_weight = 0
        rb_weight = 0
        wr_weight = 0
        te_weight = 0
        k_weight = 0
        dst_weight = 0
    else:
        qb_weight = (s_qbs+s_sflex)/(s_qbs+s_rbs+s_wrs+s_tes+s_flex+s_sflex+s_ks+s_dsts)
        rb_weight = (s_rbs+s_flex+s_sflex)/(s_qbs+s_rbs+s_wrs+s_tes+s_flex+s_sflex+s_ks+s_dsts)
        wr_weight = (s_wrs+s_flex+s_sflex)/(s_qbs+s_rbs+s_wrs+s_tes+s_flex+s_sflex+s_ks+s_dsts)
        te_weight = (s_tes+s_flex+s_sflex)/(s_qbs+s_rbs+s_wrs+s_tes+s_flex+s_sflex+s_ks+s_dsts)
        k_weight = (s_ks)/(s_qbs+s_rbs+s_wrs+s_tes+s_flex+s_sflex+s_ks+s_dsts)
        dst_weight = (s_dsts)/(s_qbs+s_rbs+s_wrs+s_tes+s_flex+s_sflex+s_ks+s_dsts)

    # Create df with those weights
    all_weights = pd.DataFrame(
    {"Pos": ["QB", "RB", "WR", "TE", "K", "D/ST"],
        "Weight": [qb_weight, rb_weight, wr_weight, te_weight, k_weight, dst_weight]})  

    # Merge weights into bench_df
    bench_weights_df = bench_df.merge(all_weights, on = "Pos")
    bench_weights_df["Weighted PPG"] = bench_weights_df[scoring]*bench_weights_df["Weight"]

    # Divide each of those weights by the number on the bench
    qbs_on_bench = bench_weights_df[bench_weights_df["Pos"] == "QB"].shape[0]
    rbs_on_bench = bench_weights_df[bench_weights_df["Pos"] == "RB"].shape[0]
    wrs_on_bench = bench_weights_df[bench_weights_df["Pos"] == "WR"].shape[0]
    tes_on_bench = bench_weights_df[bench_weights_df["Pos"] == "TE"].shape[0]
    ks_on_bench = bench_weights_df[bench_weights_df["Pos"] == "K"].shape[0]
    dsts_on_bench = bench_weights_df[bench_weights_df["Pos"] == "D/ST"].shape[0]

    # Adjust weights to reflect that number
    if qbs_on_bench != 0:
        adj_qb_weight = qb_weight/qbs_on_bench
    else:
        adj_qb_weight = 0

    if rbs_on_bench != 0:
        adj_rb_weight = rb_weight/rbs_on_bench
    else:
        adj_rb_weight = 0        

    if wrs_on_bench != 0:
        adj_wr_weight = wr_weight/wrs_on_bench
    else:
        adj_wr_weight = 0

    if tes_on_bench != 0:
        adj_te_weight = te_weight/tes_on_bench
    else:
        adj_te_weight = 0

    if ks_on_bench != 0:
        adj_k_weight = k_weight/ks_on_bench
    else:
        adj_k_weight = 0

    if dsts_on_bench != 0:
        adj_dst_weight = dst_weight/dsts_on_bench
    else:
        adj_dst_weight = 0

    # Create df with those adj weights
    adj_weights = pd.DataFrame(
    {"Pos": ["QB", "RB", "WR", "TE", "K", "D/ST"],
        "Weight": [adj_qb_weight, adj_rb_weight, adj_wr_weight, adj_te_weight, adj_k_weight, adj_dst_weight]}) 

    # Merge weights into bench_df
    adj_bench_weights_df = bench_df.merge(adj_weights, on = "Pos")
    adj_bench_weights_df["Weighted PPG"] = adj_bench_weights_df[scoring]*adj_bench_weights_df["Weight"]
    
    #################################################
    ########## Trade Partners Adjusted PPG ##########
    #################################################

    ### Calculate Total Roster Adjusted PPG ###

    # Create df with those weights
    all_weights = pd.DataFrame(
    {"Pos": ["QB", "RB", "WR", "TE", "K", "D/ST"],
        "Weight": [qb_weight, rb_weight, wr_weight, te_weight, k_weight, dst_weight]})  

    # Merge weights into bench_df
    trade_partner_bench_weights_df = trade_partner_bench_df.merge(all_weights, on = "Pos")

    trade_partner_bench_weights_df["Weighted PPG"] = trade_partner_bench_weights_df[scoring]*trade_partner_bench_weights_df["Weight"]

    # Divide each of those weights by the number on the bench
    qbs_on_bench = trade_partner_bench_weights_df[trade_partner_bench_weights_df["Pos"] == "QB"].shape[0]
    rbs_on_bench = trade_partner_bench_weights_df[trade_partner_bench_weights_df["Pos"] == "RB"].shape[0]
    wrs_on_bench = trade_partner_bench_weights_df[trade_partner_bench_weights_df["Pos"] == "WR"].shape[0]
    tes_on_bench = trade_partner_bench_weights_df[trade_partner_bench_weights_df["Pos"] == "TE"].shape[0]
    ks_on_bench = trade_partner_bench_weights_df[trade_partner_bench_weights_df["Pos"] == "K"].shape[0]
    dsts_on_bench = trade_partner_bench_weights_df[trade_partner_bench_weights_df["Pos"] == "D/ST"].shape[0]

    # Adjust weights to reflect that number
    if qbs_on_bench != 0:
        adj_qb_weight = qb_weight/qbs_on_bench
    else:
        adj_qb_weight = 0

    if rbs_on_bench != 0:
        adj_rb_weight = rb_weight/rbs_on_bench
    else:
        adj_rb_weight = 0        

    if wrs_on_bench != 0:
        adj_wr_weight = wr_weight/wrs_on_bench
    else:
        adj_wr_weight = 0

    if tes_on_bench != 0:
        adj_te_weight = te_weight/tes_on_bench
    else:
        adj_te_weight = 0

    if ks_on_bench != 0:
        adj_k_weight = k_weight/ks_on_bench
    else:
        adj_k_weight = 0

    if dsts_on_bench != 0:
        adj_dst_weight = dst_weight/dsts_on_bench
    else:
        adj_dst_weight = 0

    # Create df with those adj weights
    adj_weights = pd.DataFrame(
    {"Pos": ["QB", "RB", "WR", "TE", "K", "D/ST"],
        "Weight": [adj_qb_weight, adj_rb_weight, adj_wr_weight, adj_te_weight, adj_k_weight, adj_dst_weight]}) 

    # Merge weights into bench_df
    trade_partner_adj_bench_weights_df = trade_partner_bench_df.merge(adj_weights, on = "Pos")
    trade_partner_adj_bench_weights_df["Weighted PPG"] = trade_partner_adj_bench_weights_df[scoring]*trade_partner_adj_bench_weights_df["Weight"]

    # Is it a good or bad trade?
    if og_score == (round(final_starters[scoring].sum() + adj_bench_weights_df['Weighted PPG'].sum(),2)):
        st.subheader(f":gray[This is a perfectly even trade!]")
    elif og_score < (round(final_starters[scoring].sum() + adj_bench_weights_df['Weighted PPG'].sum(),2)):
        st.subheader(f":green[You are winning this trade!]")
    else:
        st.subheader(f":red[You are losing this trade!]")
    
    # Adjusted PPG!
    st.write("My Team's New Adjusted PPG: ", round(final_starters[scoring].sum() + adj_bench_weights_df['Weighted PPG'].sum(),2))
    st.write("Trade Partner's New Adjusted PPG: ", round(trade_partner_final_starters[scoring].sum() + trade_partner_adj_bench_weights_df['Weighted PPG'].sum(),2))
    
    # Sort
    my_post_trade_roster = my_post_trade_roster.sort_values(by = ['Pos', scoring], ascending=False)
    opponent_post_trade_roster = opponent_post_trade_roster.sort_values(by = ['Pos', scoring], ascending=False)
    
    # Delete New Pos
    my_post_trade_roster = my_post_trade_roster[['Pos', 'Player Name', scoring]]
    opponent_post_trade_roster = opponent_post_trade_roster[['Pos', 'Player Name', scoring]]
    

    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("<h3 style='text-align: center;'>My Post Trade Team</h3>", unsafe_allow_html=True)
        st.dataframe(my_post_trade_roster, use_container_width = True)
        
    with col2:
        st.markdown("<h3 style='text-align: center;'>Opponent's Post Trade Team</h3>", unsafe_allow_html=True)
        st.dataframe(opponent_post_trade_roster, use_container_width = True)
